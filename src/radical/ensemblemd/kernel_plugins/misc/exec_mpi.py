#!/usr/bin/env python

"""Executes an MPI program passed as --exec argument. All arguments are assumed
to be passed together with the name of the program via --exec (can't generalize 
all MPI programs and their arguments!). In principle works with non-MPI 
executables, but was designed to run mpi4py python applications.

Note 1: bash is assumed by default. Should be generalized to support different 
shells.

Note 2: feel free to design a better solution ;-)
"""

__author__    = "Antons Treikalis <antons.treikalis@gmail.com>"
__copyright__ = "Copyright 2014, http://radical.rutgers.edu"
__license__   = "MIT"

from copy import deepcopy

from radical.ensemblemd.exceptions import ArgumentError
from radical.ensemblemd.exceptions import NoKernelConfigurationError
from radical.ensemblemd.kernel_plugins.kernel_base import KernelBase

# ------------------------------------------------------------------------------
# 
_KERNEL_INFO = {
    "name":         "misc.exec_mpi",
    "description":  "simply runs a program passed via --exec",
    "arguments":   {"--exec=":     
                        {
                        "mandatory": True,
                        "description": "a program to execute together with all arguments."
                        },
                    },
    "machine_configs": 
    {
        "*": {
            "environment"   : None,
            "pre_exec"      : None,
            "executable"    : None,
            "uses_mpi"      : True
        }
    }
}

#-------------------------------------------------------------------------------
# 
class Kernel(KernelBase):

    #---------------------------------------------------------------------------
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
        """
        """
        if resource_key not in _KERNEL_INFO["machine_configs"]:
            if "*" in _KERNEL_INFO["machine_configs"]:
                # Fall-back to generic resource key
                resource_key = "*"
            else:
                raise NoKernelConfigurationError(kernel_name=_KERNEL_INFO["name"], resource_key=resource_key)

        cfg = _KERNEL_INFO["machine_configs"][resource_key]

        # how is pre_exec passed???
        self._executable  = self.get_arg("--exec=")
        # check if we can pass args like that
        self._arguments   = self.get_raw_args()
        self._environment = cfg["environment"]
        #self._uses_mpi    = cfg["uses_mpi"]
        #self._pre_exec    = cfg["pre_exec"] 
