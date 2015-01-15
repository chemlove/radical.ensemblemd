#!/usr/bin/env python

"""A kernel that creates a new ASCII file with a given size and name.
"""

__author__    = "Vivek <vivek.balasubramanian@rutgers.edu>"
__copyright__ = "Copyright 2014, http://radical.rutgers.edu"
__license__   = "MIT"

from copy import deepcopy

from radical.ensemblemd.exceptions import ArgumentError
from radical.ensemblemd.exceptions import NoKernelConfigurationError
from radical.ensemblemd.kernel_plugins.kernel_base import KernelBase

# ------------------------------------------------------------------------------
#
_KERNEL_INFO = {
    "name":         "md.pre_grlsd_loop",
    "description":  "Splits the inputfile into 'numCUs' number of smaller files ",
    "arguments":   {"--inputfile=":
                        {
                            "mandatory": True,
                            "description": "Input filename"
                        },
                    "--numCUs=":
                        {
                            "mandatory": True,
                            "description": "No. of files to be generated"
                        }
                    },
    "machine_configs":
    {
        "*": {
            "environment"   : {"FOO": "bar"},
            "pre_exec"      : [],
            "executable"    : ".",
            "uses_mpi"      : False
        },
        "stampede.tacc.utexas.edu": {
            "environment"   : {"FOO": "bar"},
            "pre_exec"      : ["module load python"],
            "executable"    : "python",
            "uses_mpi"      : False
        },
        "archer.ac.uk": {
            "environment"   : {"FOO": "bar"},
            "pre_exec"      : ["module load python"],
            "executable"    : "python",
            "uses_mpi"      : False
        }
    }
}


# ------------------------------------------------------------------------------
#
class Kernel(KernelBase):

    # --------------------------------------------------------------------------
    #
    def __init__(self):
        """Le constructor.
        """
        super(Kernel, self).__init__(_KERNEL_INFO)

    # --------------------------------------------------------------------------
    #
    @staticmethod
    def get_name():
        return _KERNEL_INFO["name"]

    # --------------------------------------------------------------------------
    #
    def _bind_to_resource(self, resource_key):
        """(PRIVATE) Implements parent class method.
        """
        if resource_key not in _KERNEL_INFO["machine_configs"]:
            if "*" in _KERNEL_INFO["machine_configs"]:
                # Fall-back to generic resource key
                resource_key = "*"
            else:
                raise NoKernelConfigurationError(kernel_name=_KERNEL_INFO["name"], resource_key=resource_key)

        cfg = _KERNEL_INFO["machine_configs"][resource_key]

        arguments = ['spliter.py','{0}'.format(self.get_arg("--numCUs=")), '{0}'.format(self.get_arg("--inputfile="))]

        self._executable  = cfg["executable"]
        self._arguments   = arguments
        self._environment = cfg["environment"]
        self._uses_mpi    = cfg["uses_mpi"]
        self._pre_exec    = cfg["pre_exec"]
        self._post_exec   = None

    #Can I just split the file locally without doing any of the above RP stuff ??