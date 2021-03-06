.. _multiple_simulations_instances_single_analysis_instance_example:

****************************************************************
Multiple Simulations Instances, Single Analysis Instance Example
****************************************************************

This example shows how to use the Ensemble Toolkit ``SimulationAnalysis``
pattern to execute 4 iterations of a simulation analysis loop with multiple
simulation instances and a single analysis instance. We skip the ``pre_loop``
stage in this example. Each ``simulation_stage`` generates 16 new random ASCII
files. One ASCII file in each of its instances. In the ``analysis_stage``, the
ASCII files from each of the simulation instances are analyzed and character
count is performed on each of the files using one analysis instance. The output
is downloaded to the user machine.

.. code-block:: none

	[S]    [S]    [S]    [S]    [S]    [S]    [S]
	 |      |      |      |      |      |      |
	 \-----------------------------------------/
			|
			[A]
			|
	 /-----------------------------------------\
	 |      |      |      |      |      |      |
	[S]    [S]    [S]    [S]    [S]    [S]    [S]
	 |      |      |      |      |      |      |
	 \-----------------------------------------/
			|
			[A]
			

Run Locally
===========

.. warning:: In order to run this example, you need access to a MongoDB server and
			 set the ``RADICAL_PILOT_DBURL`` in your environment accordingly.
			 The format is ``mongodb://hostname:port``. Read more about it
			 MongoDB in chapter :ref:`envpreparation`.

**Step 1:** View and download the example sources :ref:`below <multiple_simulations_single_analysis>`   or find it in 
your virtualenv under ``share/radical.ensemblemd/examples/multiple_simulations_single_analysis.py``.

**Step 2:** Run this example with ``RADICAL_ENTK_VERBOSE`` set to ``REPORT`` if you want to
see log messages about simulation progress::

	RADICAL_ENTK_VERBOSE=REPORT python multiple_simulations_single_analysis.py


Once the script has finished running, you should see the character frequency files
generated by the individual ensembles  (``cfreqs-1.dat``) in the in the same
directory you launched the script in. You should see as many such files as were the
number of iterations. Each analysis stage generates the character frequency file
for all the files generated in the simulation stage every iteration.

You can generate a more verbose output by setting ``RADICAL_ENTK_VERBOSE=INFO``.

Run Remotely
============

By default, simulation and analysis stages run on one core your local machine.

.. literalinclude:: ../../../examples/multiple_simulations_single_analysis.py
	:lines: 75-85
	:language: python
	:dedent: 2

	ResourceHandle(
		resource="localhost",
		cores=1,
		walltime=30,
		username=None,
		project=None
	)

You can change the script to use a remote HPC cluster and increase the number
of cores to see how this affects the runtime of the script as the individual
simulations instances can run in parallel.

.. code-block::

	cluster = ResourceHandle(
		resource="xsede.stampede",
		cores=16,
		walltime=30,
		username=None,  # add your username here
		project=None # add your allocation or project id here if required
		database_url=None # add your mongodb url
	)

.. note:: The following script and the script in your ``share/radical.ensemblemd/user_guide/scripts`` have some additional parsing of arguments. This is unrelated to Ensemble Toolkit.

.. _multiple_simulations_single_analysis:

Example Source
==============

:download:`Download multiple_simulations_single_analysis.py <../../../examples/multiple_simulations_single_analysis.py>`

.. literalinclude:: ../../../examples/multiple_simulations_single_analysis.py
	:language: python
