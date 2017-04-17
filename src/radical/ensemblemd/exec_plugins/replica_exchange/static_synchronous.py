#!/usr/bin/env python

"""
"""

__author__    = "Antons Treikalis <antons.treikalis@gmail.com>"
__copyright__ = "Copyright 2014, http://radical.rutgers.edu"
__license__   = "MIT"

import os
import sys
import time
import math
import json
import random
import datetime
import traceback
from os import path
import radical.pilot as rp
import radical.utils as ru
from radical.ensemblemd.exceptions import NotImplementedError, EnsemblemdError
from radical.ensemblemd.exec_plugins.plugin_base import PluginBase

# ------------------------------------------------------------------------------
#
_PLUGIN_INFO = {
    "name":         "replica_exchange.static_synchronous",
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
        self.sd_shared_list = list()

    # --------------------------------------------------------------------------
    #
    def verify_pattern(self, pattern, resource):
        pass

    # --------------------------------------------------------------------------
    #
    def execute_pattern(self, pattern, resource):
        try:
            cycles = pattern.nr_cycles
            
            self._prof = ru.Profiler("re_static_synchronous")
            self._prof.prof('prepare_shared_data_start')
            pattern.prepare_shared_data()

            shared_input_file_urls = pattern.shared_urls
            shared_input_files = pattern.shared_files

            for i in range(len(shared_input_files)):

                sd_pilot = {'source': shared_input_file_urls[i],
                            'target': 'staging:///%s' % shared_input_files[i],
                            'action': rp.TRANSFER
                }

                resource._pilot.stage_in(sd_pilot)

                sd_shared = {'source': 'staging:///%s' % shared_input_files[i],
                             'target': shared_input_files[i],
                             'action': rp.COPY
                }
                self.sd_shared_list.append(sd_shared)

            self._prof.prof('prepare_shared_data_end')
            # Pilot must be active
            self._prof.prof('wait_pilots_start')
            resource._pmgr.wait_pilots(resource._pilot.uid,'Active')       
            self._prof.prof('wait_pilots_end')

            replicas = pattern.get_replicas()

            #-------------------------------------------------------------------
            # hardcoded to bulk submission for now

            if pattern.restart == True:
                dim_int = pattern.restart_object.dimension
                current_cycle = pattern.restart_object.current_cycle
            else:
                dim_int = 0
                current_cycle = 1

            dim_count = pattern.nr_dims
            dim_str = list()

            for i in range(dim_count):
                s = 'd' + str(i+1)
                dim_str.append(s)

            self._prof.prof('main_simulation_loop_start')
            #-------------------------------------------------------------------
            # main simulation loop
            for c in range(1, cycles*dim_count+1):
                self._prof.prof('md_prep_start_time_abs')
                
                c_str = '_c' + str(current_cycle) + '_d' + str(dim_int)
                md_units = []
                cus = []

                submitted_replicas = list()
                exchange_replicas  = list()
 
                self._prof.prof('get_all_groups_start__' + c_str)
                all_groups = pattern.get_all_groups(dim_int)
                self._prof.prof('get_all_groups_end__' + c_str)

                batch = list()
                r_cores = pattern.replica_cores
                for group in all_groups:
                    # assumes uniform distribution of cores
                    if ( (len(batch)+len(group))*r_cores ) <= pattern.cores:
                        batch.append(group)
                    else:
                        # we have more replicas than cores in a single group
                        if len(batch) == 0 and len(group) > pattern.cores:
                            batch.append(group)
                        elif len(batch) == 0:
                            self.get_logger().info('ERROR: batch is empty, no replicas to prepare!')
                            sys.exit(1)

                        c_replicas = list()
                        self._prof.prof('prepare_replica_for_md_start__' + c_str )
                        for group in batch:
                            for replica in group:
                                r_kernel = pattern.prepare_replica_for_md(current_cycle, dim_int, dim_str[dim_int], group, replica, self.sd_shared_list)
                                
                                if ((r_kernel._kernel.get_name()) == "md.amber"):
                                    r_kernel._bind_to_resource(resource._resource_key, pattern.name)
                                else:
                                    r_kernel._bind_to_resource(resource._resource_key)

                                # processing data directives
                                copy_out = []
                                items_out = r_kernel._kernel._copy_output_data
                                if items_out:                    
                                    for item in items_out:
                                        i_out = {
                                            'source': item,
                                            'target': 'staging:///%s' % item,
                                            'action': rp.COPY
                                        }
                                        copy_out.append(i_out)

                                copy_in = []
                                items_in = r_kernel._kernel._copy_input_data
                                if items_in:                    
                                    for item in items_in:
                                        i_in = {
                                            'source': 'staging:///%s' % item,
                                            'target': item,
                                            'action': rp.COPY
                                        }
                                        copy_in.append(i_in)
                                        
                                #-----------------------------------------------
                                cu            = rp.ComputeUnitDescription()
                                cu.name       = "md_c{cycle}_r{replica}".format(cycle=c, replica=replica.id)
                                cu.pre_exec   = r_kernel._cu_def_pre_exec
                                cu.executable = r_kernel._cu_def_executable
                                cu.post_exec  = r_kernel._cu_def_post_exec
                                cu.arguments  = r_kernel.arguments
                                cu.mpi        = r_kernel.uses_mpi
                                cu.cores      = r_kernel.cores
                                
                                in_list = []
                                if r_kernel._cu_def_input_data:
                                    in_list = in_list + r_kernel._cu_def_input_data
                                if copy_in:
                                    in_list = in_list + copy_in
                                cu.input_staging  = in_list
                                
                                out_list = []
                                if r_kernel._cu_def_output_data:
                                    out_list = out_list + r_kernel._cu_def_output_data
                                if copy_out:
                                    out_list = out_list + copy_out
                                cu.output_staging = out_list

                                c_replicas.append(cu)

                        self._prof.prof('prepare_replica_for_md_end__' + c_str )

                        self._prof.prof('submit_md_units_start__' + c_str )
                        submitted_batch = resource._umgr.submit_units(c_replicas)
                        self._prof.prof('submit_md_units_end__' + c_str )

                        submitted_replicas += submitted_batch

                        unit_ids = []
                        for item in submitted_batch:
                            unit_ids.append( item.uid )

                        self._prof.prof('wait_md_units_start__' + c_str )
                        resource._umgr.wait_units(unit_ids=unit_ids)
                        self._prof.prof('wait_md_units_end__' + c_str )

                        if len(group) < pattern.cores:
                            batch = list()
                            batch.append(group)
                        else:
                            batch = list()

                if len(batch) != 0:
                    c_replicas = list()
                    self._prof.prof('prepare_replica_for_md_start__' + c_str )
                    for group in batch:
                        for replica in group:
                            r_kernel = pattern.prepare_replica_for_md(current_cycle, dim_int, dim_str[dim_int], group, replica, self.sd_shared_list)
                            
                            if ((r_kernel._kernel.get_name()) == "md.amber"):
                                r_kernel._bind_to_resource(resource._resource_key, pattern.name)
                            else:
                                r_kernel._bind_to_resource(resource._resource_key)

                            # processing data directives
                            copy_out = []
                            items_out = r_kernel._kernel._copy_output_data
                            if items_out:                    
                                for item in items_out:
                                    i_out = {
                                        'source': item,
                                        'target': 'staging:///%s' % item,
                                        'action': rp.COPY
                                    }
                                    copy_out.append(i_out)

                            copy_in = []
                            items_in = r_kernel._kernel._copy_input_data
                            if items_in:                    
                                for item in items_in:
                                    i_in = {
                                        'source': 'staging:///%s' % item,
                                        'target': item,
                                        'action': rp.COPY
                                    }
                                    copy_in.append(i_in)
                                    
                            #-----------------------------------------------
                            cu            = rp.ComputeUnitDescription()
                            cu.name       = "md_c{cycle}_r{replica}".format(cycle=c, replica=replica.id)
                            cu.pre_exec   = r_kernel._cu_def_pre_exec
                            cu.executable = r_kernel._cu_def_executable
                            cu.post_exec  = r_kernel._cu_def_post_exec
                            cu.arguments  = r_kernel.arguments
                            cu.mpi        = r_kernel.uses_mpi
                            cu.cores      = r_kernel.cores
                            
                            in_list = []
                            if r_kernel._cu_def_input_data:
                                in_list = in_list + r_kernel._cu_def_input_data
                            if copy_in:
                                in_list = in_list + copy_in
                            cu.input_staging  = in_list
                            
                            out_list = []
                            if r_kernel._cu_def_output_data:
                                out_list = out_list + r_kernel._cu_def_output_data
                            if copy_out:
                                out_list = out_list + copy_out
                            cu.output_staging = out_list

                            c_replicas.append(cu)

                    self._prof.prof('prepare_replica_for_md_end__' + c_str )

                    self._prof.prof('submit_md_units_start__' + c_str )
                    submitted_batch = resource._umgr.submit_units(c_replicas)
                    self._prof.prof('submit_md_units_end__' + c_str )

                    submitted_replicas += submitted_batch

                    unit_ids = list()
                    for item in submitted_batch:
                        unit_ids.append( item.uid )    

                    self._prof.prof('wait_md_units_start__' + c_str )
                    resource._umgr.wait_units(unit_ids=unit_ids)
                    self._prof.prof('wait_md_units_end__' + c_str )
                    
                #---------------------------------------------------------------
                #
                if (pattern.dims[dim_str[dim_int]]['type'] == 'salt'):

                    self._prof.prof('get_all_groups_start__' + c_str)
                    all_groups = pattern.get_all_groups(dim_int, replicas)
                    self._prof.prof('get_all_groups_end__' + c_str)

                    batch = list()
                    r_cores = pattern.dims[dim_str[dim_int]]['replicas']
                    for group in all_groups:
                        if ( (len(batch)+len(group))*r_cores ) <= pattern.cores:
                            batch.append(group)
                        else:
                            if len(batch) == 0:
                                self.get_logger().info('ERROR: batch is empty, no replicas to prepare!')
                                sys.exit(1)

                            e_replicas = list()
                            self._prof.prof('prepare_replica_for_exchange_start__' + c_str)
                            for group in batch:
                                for replica in group:
                                    r_kernel = pattern.prepare_replica_for_exchange(current_cycle, dim_int, dim_str[dim_int], group, replica, self.sd_shared_list)
                                    
                                    if ((r_kernel._kernel.get_name()) == "md.amber"):
                                        r_kernel._bind_to_resource(resource._resource_key, pattern.name)
                                    else:
                                        r_kernel._bind_to_resource(resource._resource_key)

                                    # processing data directives
                                    copy_out = []
                                    items_out = r_kernel._kernel._copy_output_data
                                    if items_out:                    
                                        for item in items_out:
                                            i_out = {
                                                'source': item,
                                                'target': 'staging:///%s' % item,
                                                'action': rp.COPY
                                            }
                                            copy_out.append(i_out)

                                    copy_in = []
                                    items_in = r_kernel._kernel._copy_input_data
                                    if items_in:                    
                                        for item in items_in:
                                            i_in = {
                                                'source': 'staging:///%s' % item,
                                                'target': item,
                                                'action': rp.COPY
                                            }
                                            copy_in.append(i_in)
                                            
                                    #-----------------------------------------------
                                    cu            = rp.ComputeUnitDescription()
                                    cu.name       = "ex_c{cycle}_r{replica}".format(cycle=c, replica=replica.id)
                                    cu.pre_exec   = r_kernel._cu_def_pre_exec
                                    cu.executable = r_kernel._cu_def_executable
                                    cu.post_exec  = r_kernel._cu_def_post_exec
                                    cu.arguments  = r_kernel.arguments
                                    cu.mpi        = r_kernel.uses_mpi
                                    cu.cores      = r_kernel.cores
                                    
                                    in_list = []
                                    if r_kernel._cu_def_input_data:
                                        in_list = in_list + r_kernel._cu_def_input_data
                                    if copy_in:
                                        in_list = in_list + copy_in
                                    cu.input_staging  = in_list
                                    
                                    out_list = []
                                    if r_kernel._cu_def_output_data:
                                        out_list = out_list + r_kernel._cu_def_output_data
                                    if copy_out:
                                        out_list = out_list + copy_out
                                    cu.output_staging = out_list

                                    e_replicas.append(cu)

                            self._prof.prof('prepare_replica_for_exchange_end__' + c_str)

                            self._prof.prof('submit_ex_units_start__' + c_str )
                            exchange_replicas += resource._umgr.submit_units(e_replicas) 
                            self._prof.prof('submit_ex_units_end__' + c_str )
 
                            self._prof.prof('wait_ex_units_start__' + c_str )
                            resource._umgr.wait_units()
                            self._prof.prof('wait_ex_units_end__' + c_str )
 
                            batch = list()
                            batch.append(group)
                    if len(batch) != 0:
                        e_replicas = list()
                        self._prof.prof('prepare_replica_for_exchange_start__' + c_str)
                        for group in batch:
                            for replica in group:
                                r_kernel = pattern.prepare_replica_for_exchange(current_cycle, dim_int, dim_str[dim_int], group, replica, self.sd_shared_list)
                                
                                if ((r_kernel._kernel.get_name()) == "md.amber"):
                                    r_kernel._bind_to_resource(resource._resource_key, pattern.name)
                                else:
                                    r_kernel._bind_to_resource(resource._resource_key)

                                # processing data directives
                                copy_out = []
                                items_out = r_kernel._kernel._copy_output_data
                                if items_out:                    
                                    for item in items_out:
                                        i_out = {
                                            'source': item,
                                            'target': 'staging:///%s' % item,
                                            'action': rp.COPY
                                        }
                                        copy_out.append(i_out)

                                copy_in = []
                                items_in = r_kernel._kernel._copy_input_data
                                if items_in:                    
                                    for item in items_in:
                                        i_in = {
                                            'source': 'staging:///%s' % item,
                                            'target': item,
                                            'action': rp.COPY
                                        }
                                        copy_in.append(i_in)
                                        
                                #-----------------------------------------------
                                cu            = rp.ComputeUnitDescription()
                                cu.name       = "ex_c{cycle}_r{replica}".format(cycle=c, replica=replica.id)
                                cu.pre_exec   = r_kernel._cu_def_pre_exec
                                cu.executable = r_kernel._cu_def_executable
                                cu.post_exec  = r_kernel._cu_def_post_exec
                                cu.arguments  = r_kernel.arguments
                                cu.mpi        = r_kernel.uses_mpi
                                cu.cores      = r_kernel.cores
                                
                                in_list = []
                                if r_kernel._cu_def_input_data:
                                    in_list = in_list + r_kernel._cu_def_input_data
                                if copy_in:
                                    in_list = in_list + copy_in
                                cu.input_staging  = in_list
                                
                                out_list = []
                                if r_kernel._cu_def_output_data:
                                    out_list = out_list + r_kernel._cu_def_output_data
                                if copy_out:
                                    out_list = out_list + copy_out
                                cu.output_staging = out_list

                                e_replicas.append(cu)

                        self._prof.prof('prepare_replica_for_exchange_end__' + c_str)

                        self._prof.prof('submit_ex_units_start__' + c_str )
                        exchange_replicas += resource._umgr.submit_units(e_replicas)
                        self._prof.prof('submit_ex_units_end__' + c_str )

                        self._prof.prof('wait_ex_units_start__' + c_str )
                        resource._umgr.wait_units()
                        self._prof.prof('wait_ex_units_end__' + c_str )

                    #-----------------------------------------------------------
                    # submitting unit which determines exchanges between replicas
                  
                    self._prof.prof('prepare_global_ex_calc_start__' + c_str )
                    gl_kernel = pattern.prepare_global_ex_calc(current_cycle, dim_int, dim_str[dim_int], self.sd_shared_list)
                    
                    gl_kernel._bind_to_resource(resource._resource_key)

                    copy_out = []
                    items_out = gl_kernel._kernel._copy_output_data
                    if items_out:                    
                        for item in items_out:
                            i_out = {
                                'source': item,
                                'target': 'staging:///%s' % item,
                                'action': rp.COPY
                            }
                            copy_out.append(i_out)

                    copy_in = []
                    items_in = gl_kernel._kernel._copy_input_data
                    if items_in:                    
                        for item in items_in:
                            i_in = {
                                'source': 'staging:///%s' % item,
                                'target': item,
                                'action': rp.COPY
                            }
                            copy_in.append(i_in)
                            
                    #-----------------------------------------------
                    cu            = rp.ComputeUnitDescription()
                    cu.name       = "gl_c{cycle}_r{replica}".format(cycle=c, replica=replica.id)
                    cu.pre_exec   = gl_kernel._cu_def_pre_exec
                    cu.executable = gl_kernel._cu_def_executable
                    cu.post_exec  = gl_kernel._cu_def_post_exec
                    cu.arguments  = gl_kernel.arguments
                    cu.mpi        = gl_kernel.uses_mpi
                    cu.cores      = gl_kernel.cores
                    
                    in_list = []
                    if gl_kernel._cu_def_input_data:
                        in_list = in_list + gl_kernel._cu_def_input_data
                    if copy_in:
                        in_list = in_list + copy_in
                    cu.input_staging  = in_list
                    
                    out_list = []
                    if gl_kernel._cu_def_output_data:
                        out_list = out_list + gl_kernel._cu_def_output_data
                    if copy_out:
                        out_list = out_list + copy_out
                    cu.output_staging = out_list

                    self._prof.prof('prepare_global_ex_calc_end__' + c_str )

                    self._prof.prof('submit_gl_unit_start__' + c_str )
                    global_ex_cu = resource._umgr.submit_units(cu)
                    self._prof.prof('submit_gl_unit_end__' + c_str )
                    
                    self._prof.prof('wait_gl_unit_start__' + c_str )
                    resource._umgr.wait_units(global_ex_cu.uid)
                    self._prof.prof('wait_gl_unit_end__' + c_str )

                #---------------------------------------------------------------
                # no salt concentration exchange
                else:
                    self._prof.prof('prepare_global_ex_calc_start__' + c_str )
                    gl_kernel = pattern.prepare_global_ex_calc(current_cycle, dim_int, dim_str[dim_int], self.sd_shared_list)
                    
                    gl_kernel._bind_to_resource(resource._resource_key)

                    copy_out = []
                    items_out = gl_kernel._kernel._copy_output_data
                    if items_out:                    
                        for item in items_out:
                            i_out = {
                                'source': item,
                                'target': 'staging:///%s' % item,
                                'action': rp.COPY
                            }
                            copy_out.append(i_out)

                    copy_in = []
                    items_in = gl_kernel._kernel._copy_input_data
                    if items_in:                    
                        for item in items_in:
                            i_in = {
                                'source': 'staging:///%s' % item,
                                'target': item,
                                'action': rp.COPY
                            }
                            copy_in.append(i_in)
                            
                    #-----------------------------------------------------------
                    cu            = rp.ComputeUnitDescription()
                    cu.name       = "gl_c{cycle}_r{replica}".format(cycle=c, replica=replica.id)
                    cu.pre_exec   = gl_kernel._cu_def_pre_exec
                    cu.executable = gl_kernel._cu_def_executable
                    cu.post_exec  = gl_kernel._cu_def_post_exec
                    cu.arguments  = gl_kernel.arguments
                    cu.mpi        = gl_kernel.uses_mpi
                    cu.cores      = gl_kernel.cores
                    
                    in_list = []
                    if gl_kernel._cu_def_input_data:
                        in_list = in_list + gl_kernel._cu_def_input_data
                    if copy_in:
                        in_list = in_list + copy_in
                    cu.input_staging  = in_list
                    
                    out_list = []
                    if gl_kernel._cu_def_output_data:
                        out_list = out_list + gl_kernel._cu_def_output_data
                    if copy_out:
                        out_list = out_list + copy_out
                    cu.output_staging = out_list

                    self._prof.prof('prepare_global_ex_calc_end__' + c_str )

                    self._prof.prof('submit_gl_unit_start__' + c_str )
                    global_ex_cu = resource._umgr.submit_units(cu)
                    self._prof.prof('submit_gl_unit_end__' + c_str )
                    
                    self._prof.prof('wait_gl_unit_start__' + c_str )
                    resource._umgr.wait_units(global_ex_cu.uid)
                    self._prof.prof('wait_gl_unit_end__' + c_str )

                #---------------------------------------------------------------
                # check for failures
                failed_cus = list()           
                for r in submitted_replicas:
                    if r.state != rp.DONE:
                        self.get_logger().info('ERROR: In D%d MD-step failed for unit:  %s' % (dim_int, r.uid))
                        failed_cus.append( r.uid )

                if len(exchange_replicas) > 0:
                    for r in exchange_replicas:
                        if r.state != rp.DONE:
                            self.get_logger().info('ERROR: In D%d Exchange-step failed for unit:  %s' % (dim_int, r.uid))
                            failed_cus.append( r.uid )

                if global_ex_cu.state != rp.DONE:
                    self.get_logger().info('ERROR: In D%d Global-Exchange-step failed for unit:  %s' % (dim_int, global_ex_cu.uid))
                    failed_cus.append( global_ex_cu.uid )
                #
                #---------------------------------------------------------------

                # do exchange of parameters  
                self._prof.prof('do_exchange_start__' + c_str )                   
                pattern.do_exchange(current_cycle, dim_int, dim_str[dim_int], replicas)
                # for the case when we were restarting previous simulation
                pattern.restart_done = True
                self._prof.prof('do_exchange_end__' + c_str ) 

                #write replica objects out
                self._prof.prof('save_replicas_start__' + c_str ) 
                pattern.save_replicas(current_cycle, dim_int, dim_str[dim_int], replicas)
                self._prof.prof('save_replicas_end__' + c_str )

                self.get_logger().info("parameters after exchange: ")
                for r in replicas:
                    self.get_logger().info("replica: {0} type: {1} param: {2}".format(r.id, r.dims[dim_str[dim_int]]['type'], r.dims[dim_str[dim_int]]['par']) )

            #-------------------------------------------------------------------
            # end of loop
            self._prof.prof('main_simulation_loop_end')

        except KeyboardInterrupt:
            traceback.print_exc()

        self.get_logger().info("Replica Exchange simulation finished successfully!")
        self.get_logger().info("Deallocating resource.")
        resource.deallocate()
