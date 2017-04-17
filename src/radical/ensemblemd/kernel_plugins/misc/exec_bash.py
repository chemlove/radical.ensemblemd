#!/usr/bin/env python

"""A kernel that executes up to three executables using bash
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
    "name":         "misc.exec_bash",
    "description":  "Executes up to three apps using bash",
    "arguments":   {"--exec1=":     
                        {
                        "mandatory": True,
                        "description": "App one"
                        },
                    "--exec2=":     
                        {
                        "mandatory": False,
                        "description": "App two"
                        },
                    "--exec3=":     
                        {
                        "mandatory": False,
                        "description": "App three"
                        },
                    },
    "machine_configs": 
    {
        "*": {
            "environment"   : None,
            "pre_exec"      : None,
            "executable"    : "/bin/bash",
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

        exec1 = self.get_arg("--exec1=")
        exec2 = self.get_arg("--exec2=")
        exec3 = self.get_arg("--exec3=")

        if (exec2 and exec3):
            arguments  = ['-c', exec1 + "; wait; " + \
                                exec2 + "; wait; " + \
                                exec3 ]
        else:
            arguments  = ['-c', exec1 + "; wait; " + \
                                exec2 ]
        
        self._executable  = "/bin/bash"
        self._arguments   = arguments
        self._environment = cfg["environment"]
        self._uses_mpi    = cfg["uses_mpi"]
        #self._pre_exec    = None 

