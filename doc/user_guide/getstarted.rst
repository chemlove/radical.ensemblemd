.. _getstarted:

***************
Getting Started
***************

In this section we will run you through the basics building blocks of the  API.
We will develop an example application, starting from a singe task, to a bag
of tasks, to a Pipeline of tasks.

.. note:: The reader is assumed to be familiar with the general Ensemble MD concepts as described in :ref:`introduction` and :ref:`overview`.

.. note:: This chapter assumes that you have successfully installed Ensemble MD, and also configured access to the resources you intent to use for the examples (see chapter :ref:`Installation`).

You can download the complete code discussed in this section :download:`here <examples/get_started.py>`.

Importing components from the Ensemble MD Module
===========================================================

To create any application using EnsembleMD, you would need to import three modules: Kernel, Pattern, Execution Context. The Pattern imported depends on the application requirement. We have already discussed these components in the earlier sections. The ``EnsemblemdError`` module is imported for proper reporting of any errors.

.. code-block:: python
    

    from radical.ensemblemd import Kernel
    from radical.ensemblemd import Pipeline
    from radical.ensemblemd import EnsemblemdError
    from radical.ensemblemd import SingleClusterEnvironment



Creating an Execution Context
================================

We create an execution context in order to get access to a machine and acquire resources on that machine. In the 
following snipper of code, we create an execution context of ``SingleClusterEnvironment`` type which gives access to 
a single machine. We create it targetting the local machine, requesting 1 core for a period of 15 mins. The 'username' 
and 'allocation' are required machines where there is a different username and an allocation number required. The 
'database_url' specific the mongodb instance to be used.

.. code-block:: python
    

     cluster = SingleClusterEnvironment(
                        resource="localhost",
                        cores=1,
                        walltime=15,
                        username=None,
                        allocation=None,
                        database_name="mongod:mymongodburl"
                    )

Once created, you can now perform the following operations:

* allocate(): allocates the resources on the HPC cluster.
* run(pattern): takes a execution pattern instance and executes it on the HPC cluster.
* deallocate(): terminates the job running on the HPC cluster

Creating the Execution Pattern class
========================================

Next, we create an execution pattern class. The pattern class needs to import the specific pattern the application requires. In this case, we import the Pipeline class. We simply create our own class ``MyApp`` that is of the Pipeline pattern type.

.. code-block:: python
    

      class MyApp(Pipeline):
       def __init__(self, steps, instances):
           Pipeline.__init__(self, steps, instances)


Once the class type is defined, we can now define ``steps`` to this pattern. Each step of the pattern can have different workloads. We now instantiate this class,

.. code-block:: python
    
    
    app = MyApp(steps=1, instances=1)

We have created an instance of the class with 1 step and 1 instance. The instance here refers to the number of 
instances of the step to be executed (in other words the number of tasks with the same kernel as in a particular step).

A complete look at our  pattern class,

.. code-block:: python
    

      class MyApp(Pipeline):
            def __init__(self, steps, instances):
                    Pipeline.__init__(self, instances)


            def step_1(self,instance):
                    <define what to do> 


      app = MyApp(steps=1, instances=1)



Using the Kernel Plugin 
===========================

Well, we have now designed the application class completely. We can define what the first step of the application 
needs to execute. We use the kernels to ``define what to do`` in the first step.

.. code-block:: python
    

    k = Kernel(name="misc.hello")
    k.arguments = ["--file=output_{0}.txt".format(instance)]


We use the kernel ``misc.hello`` already predefined in EnsembleMD. This kernel creates a file (if it does not exist alread) with the name as defined in the argument and prints a **Hello World** within it. 


Ok, so by now we have seen how to create an execution context, define a pattern and add a kernel to the pattern. To specify the pattern to be exeted on the resources is simple:

.. code-block:: python
    

    cluster.run(myapp)
    cluster.deallocate()

We deallocate the resources once the application has finished executing.

And that's it ! That's all the steps of the pattern. Let's take a look at the complete code in the example.

.. literalinclude:: examples/get_started.py

.. note::

      You can use the Pipeline pattern to create a Bag of Tasks by having only one step. In this case, this is an example of a Bag of Tasks with a bag size of 1.

To run the script, simply do the following from command line:

::

     python myapp.py

