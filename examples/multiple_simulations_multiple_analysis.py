#!/usr/bin/env python

"""

This example shows how to use the Ensemble MD Toolkit ``SimulationAnalysis``
pattern to execute 4 iterations of a simulation analysis loop with multiple
simulation instances and multiple analysis instances. We skip the ``pre_loop``
step in this example. Each ``simulation_step`` generates 16 new random ASCII
files. One ASCII file in each of its instances. In the ``analysis_step``,
the ASCII files from the simulation instances are analyzed and character
count is performed. Each analysis instance uses the file generated by the
corresponding simulation instance. This is possible since we use the same
number of instances for simulation and analysis.The output is downloaded to
the user machine.

.. code-block:: none

    [S]    [S]    [S]    [S]    [S]    [S]    [S]    [S]
     |      |      |      |      |      |      |      |
    [A]    [A]    [A]    [A]    [A]    [A]    [A]    [A]
     |      |      |      |      |      |      |      |
    [S]    [S]    [S]    [S]    [S]    [S]    [S]    [S]
     |      |      |      |      |      |      |      |
    [A]    [A]    [A]    [A]    [A]    [A]    [A]    [A]
     :      :      :      :      :      :      :      :

Run Locally
^^^^^^^^^^^

.. warning:: In order to run this example, you need access to a MongoDB server and
             set the ``RADICAL_PILOT_DBURL`` in your environment accordingly.
             The format is ``mongodb://hostname:port``. Read more about it
             MongoDB in chapter :ref:`envpreparation`.

**Step 1:** View and download the example sources :ref:`below <multiple_simulations_multiple_analysis>`.

**Step 2:** Run this example with ``RADICAL_ENMD_VERBOSE`` set to ``info`` if you want to
see log messages about simulation progress::

    RADICAL_ENMD_VERBOSE=info python multiple_simulations_multiple_analysis.py

Once the script has finished running, you should see the character frequency files
generated by the individual ensembles  (``cfreqs-1-1.dat``) in the in the same
directory you launched the script in. You should see as many such files as were the
number of iterations times the number of ensembles (i.e. simulation/analysis width).
Each analysis stage generates the character frequency file for each of the files
generated in the simulation stage every iteration.

Run Remotely
^^^^^^^^^^^^

By default, simulation and analysis steps run on one core your local machine::

    SingleClusterEnvironment(
        resource="localhost",
        cores=1,
        walltime=30,
        username=None,
        allocation=None
    )

You can change the script to use a remote HPC cluster and increase the number
of cores to see how this affects the runtime of the script as the individual
pipeline instances can run in parallel::

    SingleClusterEnvironment(
        resource="stampede.tacc.utexas.edu",
        cores=16,
        walltime=30,
        username=None,  # add your username here
        allocation=None # add your allocation or project id here if required
    )



.. _multiple_simulations_multiple_analysis:

Example Source
^^^^^^^^^^^^^^
"""

__author__       = "Vivek <vivek.balasubramanian@rutgers.edu>"
__copyright__    = "Copyright 2014, http://radical.rutgers.edu"
__license__      = "MIT"
__example_name__ = "Multiple Simulations Instances, Multiple Analysis Instances Example (MSMA)"

from radical.ensemblemd import Kernel
from radical.ensemblemd import SimulationAnalysisLoop
from radical.ensemblemd import EnsemblemdError
from radical.ensemblemd import SingleClusterEnvironment

# ------------------------------------------------------------------------------
#
class MSMA(SimulationAnalysisLoop):
    """MSMA exemplifies how the MSMA (Multiple-Simulations / Multiple-Analsysis)
       scheme can be implemented with the SimulationAnalysisLoop pattern.
    """
    def __init__(self, iterations, simulation_instances, analysis_instances):
        SimulationAnalysisLoop.__init__(self, iterations, simulation_instances, analysis_instances)


    def simulation_step(self, iteration, instance):
        """In the simulation step we
        """
        k = Kernel(name="misc.mkfile")
        k.arguments = ["--size=1000", "--filename=asciifile.dat"]
        return k

    def analysis_step(self, iteration, instance):
        """In the analysis step we use the ``$PREV_SIMULATION`` data reference
           to refer to the previous simulation. The same
           instance is picked implicitly, i.e., if this is instance 5, the
           previous simulation with instance 5 is referenced.
        """
        k = Kernel(name="misc.ccount")
        k.arguments            = ["--inputfile=asciifile.dat", "--outputfile=cfreqs.dat"]
        k.link_input_data      = "$PREV_SIMULATION/asciifile.dat".format(instance=instance)
        k.download_output_data = "cfreqs.dat > cfreqs-{iteration}-{instance}.dat".format(instance=instance, iteration=iteration)
        return k


# ------------------------------------------------------------------------------
#
if __name__ == "__main__":

    try:
        # Create a new static execution context with one resource and a fixed
        # number of cores and runtime.
        cluster = SingleClusterEnvironment(
            resource="localhost",
            cores=1,
            walltime=30,
            username=None,
            allocation=None
        )

        # Allocate the resources.
        cluster.allocate()

        # We set both the the simulation and the analysis step 'instances' to 8.
        msma = MSMA(iterations=2, simulation_instances=8, analysis_instances=8)

        cluster.run(msma)

    except EnsemblemdError, er:

        print "Ensemble MD Toolkit Error: {0}".format(str(er))
        raise # Just raise the execption again to get the backtrace