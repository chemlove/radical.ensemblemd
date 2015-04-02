#!/usr/bin/env python

"""A static execution plugin RE pattern 2
For this pattern exchange is synchronous - all replicas must finish MD run before
an exchange can take place and all replicas must participate. Exchange is performed
on compute
"""

__author__    = "Antons Treikalis <antons.treikalis@rutgers.edu>"
__copyright__ = "Copyright 2014, http://radical.rutgers.edu"
__license__   = "MIT"

import os
import random
import time
import datetime
import radical.pilot
from radical.ensemblemd.utils import extract_timing_info

from radical.ensemblemd.exceptions import NotImplementedError, EnsemblemdError
from radical.ensemblemd.exec_plugins.plugin_base import PluginBase

# ------------------------------------------------------------------------------
#
_PLUGIN_INFO = {
    "name":         "replica_exchange.static_pattern_2",
    "pattern":      "ReplicaExchange",
    "context_type": "Static"
}

_PLUGIN_OPTIONS = []

STAGING_AREA = 'staging_area'

# ------------------------------------------------------------------------------
#
class Plugin(PluginBase):

    # --------------------------------------------------------------------------
    #
    def __init__(self):
        super(Plugin, self).__init__(_PLUGIN_INFO, _PLUGIN_OPTIONS)

    # --------------------------------------------------------------------------
    #
    def verify_pattern(self, pattern, resource):
        pass

    # --------------------------------------------------------------------------
    #
    def execute_pattern(self, pattern, resource):
        try:
            cycles = pattern.nr_cycles+1
            pattern._execution_profile = []
            all_cus = []
 
            # shared data
            pattern.prepare_shared_data()

            shared_input_file_urls = pattern.shared_urls
            shared_input_files = pattern.shared_files
            sd_shared_list = []

            for i in range(len(shared_input_files)):

                sd_pilot = {'source': shared_input_file_urls[i],
                            'target': 'staging:///%s' % shared_input_files[i],
                            'action': radical.pilot.TRANSFER
                }

                resource._pilot.stage_in(sd_pilot)

                sd_shared = {'source': 'staging:///%s' % shared_input_files[i],
                             'target': shared_input_files[i],
                             'action': radical.pilot.COPY
                }
                sd_shared_list.append(sd_shared)

            # Pilot must be active
            resource._pmgr.wait_pilots(resource._pilot.uid,'Active')       
     
            pattern_start_time = datetime.datetime.now()

            replicas = pattern.get_replicas()

            for c in range(1, cycles):

                step_timings = {
                    "name": "md_run_{0}".format(c),
                    "timings": {}
                }
                step_start_time_abs = datetime.datetime.now()

                md_units = []
                for r in replicas:

                    self.get_logger().info("Cycle %d: Building input files for replica %d" % ((c), r.id) )
                    pattern.build_input_file(r)
                    self.get_logger().info("Cycle %d: Preparing replica %d for MD run" % ((c), r.id) )
                    r_kernel = pattern.prepare_replica_for_md(r)

                    if ((r_kernel._kernel.get_name()) == "md.amber"):
                        r_kernel._bind_to_resource(resource._resource_key, pattern.name)
                    else:
                        r_kernel._bind_to_resource(resource._resource_key)

                    # processing data directives
                    # need means to distinguish between copy and link
                    copy_out = []
                    items_out = r_kernel._kernel._copy_output_data
                    for item in items_out:
                        i_out = {
                            'source': item,
                            'target': 'staging:///%s' % item,
                            'action': radical.pilot.COPY
                        }
                        copy_out.append(i_out)

                    cu                = radical.pilot.ComputeUnitDescription()
                    cu.name = "md ;{cycle} ;{replica}".format(cycle=c, replica=r.id)
                    cu.pre_exec       = r_kernel._cu_def_pre_exec
                    cu.executable     = r_kernel._cu_def_executable
                    cu.arguments      = r_kernel.arguments
                    cu.mpi            = r_kernel.uses_mpi
                    cu.cores          = r_kernel.cores
                    cu.input_staging  = sd_shared_list + r_kernel._cu_def_input_data
                    cu.output_staging = copy_out + r_kernel._cu_def_output_data

                    sub_replica = resource._umgr.submit_units(cu)
                    md_units.append(sub_replica)                    

                all_cus.extend(md_units)
         
                self.get_logger().info("Cycle %d: Performing MD step for replicas" % (c) )

                resource._umgr.wait_units()
                step_end_time_abs = datetime.datetime.now()          
 
                failed_units = ""
                for unit in md_units:
                    if unit.state != radical.pilot.DONE:
                        failed_units += " * MD step: Unit {0} failed with an error: {1}\n".format(unit.uid, unit.stderr)

                # Process CU information and append it to the dictionary
                tinfo = extract_timing_info(md_units, pattern_start_time, step_start_time_abs, step_end_time_abs)
                for key, val in tinfo.iteritems():
                    step_timings['timings'][key] = val

                # Write the whole thing to the profiling dict
                pattern._execution_profile.append(step_timings)

                if (c < cycles):
                    step_timings = {
                        "name": "ex_run_{0}".format(c),
                        "timings": {}
                    }
                    step_start_time_abs = datetime.datetime.now()

                    ex_units = []
                    # computing swap matrix
                    for r in replicas:

                        self.get_logger().info("Cycle %d: Preparing replica %d for Exchange run" % ((c), r.id) )
                        ex_kernel = pattern.prepare_replica_for_exchange(r)
                        ex_kernel._bind_to_resource(resource._resource_key)
                        
                        cu                = radical.pilot.ComputeUnitDescription()
                        cu.name = "ex ;{cycle} ;{replica}".format(cycle=c, replica=r.id)
                        cu.pre_exec       = ex_kernel._cu_def_pre_exec
                        cu.executable     = ex_kernel._cu_def_executable
                        cu.arguments      = ex_kernel.arguments
                        cu.mpi            = ex_kernel.uses_mpi
                        cu.cores          = ex_kernel.cores
                        cu.input_staging  = ex_kernel._cu_def_input_data
                        cu.output_staging = ex_kernel._cu_def_output_data

                        sub_replica = resource._umgr.submit_units(cu)
                        ex_units.append(sub_replica)

                    self.get_logger().info("Cycle %d: Performing Exchange step for replicas" % (c) )
                    resource._umgr.wait_units()
                    step_end_time_abs = datetime.datetime.now()
                    all_cus.extend(ex_units)

                    failed_units = ""
                    for unit in ex_units:
                        if unit.state != radical.pilot.DONE:
                            failed_units += " * EX step: Unit {0} failed with an error: {1}\n".format(unit.uid, unit.stderr)

                    # Process CU information and append it to the dictionary
                    tinfo = extract_timing_info(ex_units, pattern_start_time, step_start_time_abs, step_end_time_abs)

                    for key, val in tinfo.iteritems():
                        step_timings['timings'][key] = val

                    # Write the whole thing to the profiling dict
                    pattern._execution_profile.append(step_timings)

                    step_timings = {
                        "name": "post_processing_{0}".format(c),
                        "timings": {}
                    }
                    step_start_time_abs = datetime.datetime.now()

                    matrix_columns = []
                    for r in ex_units:
                        d = str(r.stdout)
                        data = d.split()
                        matrix_columns.append(data)

                    # computing swap matrix
                    self.get_logger().info("Cycle %d: Composing swap matrix" % (c) )
                    swap_matrix = pattern.get_swap_matrix(replicas, matrix_columns)

                    # this is actual exchange
                    for r_i in replicas:
                        r_j = pattern.exchange(r_i, replicas, swap_matrix)
                        if (r_j != r_i):
                            self.get_logger().info("Performing exchange of parameters between replica %d and replica %d" % ( r_j.id, r_i.id ))
                            # swap parameters
                            pattern.perform_swap(r_i, r_j)

                    step_end_time_abs = datetime.datetime.now()

                    # processing timings
                    step_start_time_rel = step_start_time_abs - pattern_start_time
                    step_end_time_rel = step_end_time_abs - pattern_start_time

                    tinfo = {
                                "step_start_time": {
                                    "abs": step_start_time_abs,
                                    "rel": step_start_time_rel
                                },
                                "step_end_time": {
                                    "abs": step_end_time_abs,
                                    "rel": step_end_time_rel
                                }
                            }

                    for key, val in tinfo.iteritems():
                        step_timings['timings'][key] = val

                    # Write the whole thing to the profiling dict
                    pattern._execution_profile.append(step_timings)
    
            # End of simulation loop
            #------------------------
            
        except Exception, ex:
            self.get_logger().exception("Fatal error during execution: {0}.".format(str(ex)))
            raise

        self.get_logger().info("Replica Exchange simulation finished successfully!")
        self.get_logger().info("Deallocating resource.")
        resource.deallocate()

