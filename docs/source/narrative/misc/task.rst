.. _tasks:

=====
Tasks
=====

.. contents:: :local:

Introduction
============

You can achieve responsive page rendering by offloading long running blocking calls from HTTP request processing to external worker processes. Websauna uses :ref:`Celery` for asynchronous task processing. Celery allows asynchronous execution of delayed and scheduled tasks.

Installation
============

Make sure you have installed Websauna with ``celery`` extra dependencies to use tasks:

.. code-block:: shell

    pip install websauna[celery]

See :ref:`installing_websauna` for more information. Websauna requires Celery 4.0 or newer.

Configuring Celery
==================

Websauna configures Celery using :ref:`websauna.celery_config` directive in INI settings.

Celery is configured to use :term:`Redis` as a broker between web and task processes. Unless you want to add your own scheduled tasks you do not need to change ``websauna.celery_config`` setting.

Running Celery
==============

Celery runs separate long running processes called *workers* to execute the tasks. Furthermore a separate process called *beat* needs to be run to initiate scheduled tasks. Below is an example how to run Celery on your development installation.

.. note :::

    For local development you don't need to run full Celery setup on your computer. Instead you set Celery tasks to eager execution. This means that delayed tasks are run immediately blocking the HTTP response. See **task_always_eager** Celery configuration variable. This is turned on with the default *development.ini*.

Use :ref:`ws-celery` command to run Celery. ``ws-celery`` is a wrapper around ``celery`` command supporting reading settings from :ref:`INI configuration files <config>`.

To launch a Celery worker:

.. code-block: shell

    ws-celery myapp/conf/development.ini -- worker

To launch a Celery beat do:

.. code-block: shell

    ws-celery myapp/conf/development.ini -- beat

Below is a ``run-celery.bash`` script to manage Celery for local development:

.. code-block:: bash

    #!/bin/bash
    # Launch both celery processes and kill when this script exits.
    # This script is good for running Celery for local development.
    #

    set -e
    set -u

    # http://stackoverflow.com/a/360275/315168
    trap 'pkill -f ws-celery' EXIT

    # celery command implicitly overrides root log level,
    # let's at least state it explicitly here
    ws-celery myapp/conf/development.ini -- worker --loglevel=debug &
    ws-celery myapp/conf/development.ini -- beat --loglevel=debug &

    # Wait for CTRL+C
    sleep 99999999

Managing tasks
==============

You need to register your tasks with Celery. You do this by decorating your task functions :py:func:`websauna.system.task.tasks.task` function decorator. The decorated functions and their modules must be scanned using ``self.config.scan()`` in :py:meth:`websauna.system.Initializer.configure_tasks` of your app Initializer class.

Accessing request within tasks
------------------------------

Websauna uses a custom :py:class:`websauna.system.task.celeryloader.WebsaunaLoader` Celery task loader to have ``request`` object available within your tasks. This allows you to access to ``dbsession`` and other implicit environment variables. Your tasks must have ``bind=true`` in its declaration to access the Celery task context through ``self`` argument.

Example:

.. code-block:: python

    from celery.task import Task
    from websauna.system.task.tasks import task
    from websauna.system.task.tasks import RetryableTransactionTask


    @task(base=RetryableTransactionTask, bind=True)
    def my_task(self: Task):
        # self.request is celery.app.task.Context
        # self.request.request is websauna.system.http.Request
        dbsession = self.request.request.dbsession
        # ...

Task dispatch on commit
-----------------------

One generally wants to have tasks runs only if HTTP request execution completes successfully. Websauna provides :py:class:`websauna.system.task.tasks.ScheduleOnCommitTask` task base class to do this.

Transaction retries
-------------------

If your task does database processing use :py:class:`websauna.system.task.RetryableTransactionTask` base class. It will mimic the behavior of ``pyramid_tm`` transaction retry machine. It tries to retry the transaction few times in the case of :ref:`transaction serialization conflict <occ>`.

Delayed tasks
-------------

Delayed tasks run tasks outside HTTP request processing. Delayed tasks take non-critical actions after HTTP response has been sent to make the server responsive. These kind of actions include calling third party APIs like sending email and SMS. Often third party APIs are slow and we don't want to delay page rendering for a site visitor.

Below is an example which calls third party API (Twilio SMS out) - you don't want to block page render if the third party API fails or is delayed. The API is HTTP based, so calling it adds great amount of milliseconds on the request processing. The task also adds some extra delay and the SMS is not shoot up right away - it can be delayed hour or two after the user completes an order.

.. note ::

    All task arguments must be JSON serializable. You cannot pass any SQLAlchemy objects to Celery. Instead use primary keys of database objects.

Example of deferring a task executing outside HTTP request processing in ``tasks.py``:

.. code-block:: python

    from celery.task import Task
    from websauna.system.task.tasks import task
    from websauna.system.task.tasks import RetryableTransactionTask
    # ...


    @task(base=RetryableTransactionTask, bind=True)
    def send_review_sms_notification(self: Task, delivery_id: int):

        request = self.request.request  # type: websauna.system.http.Request

        dbsession = request.dbsession
        delivery = dbsession.query(models.Delivery).get(delivery_id)
        customer = delivery.customer

        review_url = request.route_url("review_public", delivery_uuid=uuid_to_slug(delivery.uuid))

        # The following call to Twilio may take up to 2-5 seconds
        # We don't want to block HTTP response until Twilio is done sending SMS.
        sms.send_templated_sms_to_user(request, customer, "drive/sms/review.txt", locals())

Then you can schedule your task for delayed execution in ``views.py``:

.. code-block:: python

    def my_view(request):
        delivery = request.dbsession.query(Delivery).get(1)
        send_review_sms_notification.apply_async(args=(delivery.id,), tm=request.transaction_manager)

You also need to scan ``tasks.py`` in Initializer:

.. code-block:: python

    class MyAppInitializer(Initializer):
        """Entry point for tests stressting task functionality."""

        def configure_tasks(self):
            self.config.scan("myapp.tasks")

Scheduled tasks
---------------

Scheduled task is a job that is set to run on certain time interval or on a certain wall clock moment - e.g. every day 24:00.

Creating a task
~~~~~~~~~~~~~~~

Here is an example task for calling API and storing the results in Redis. In your package create file ``task.py`` and add:

.. code-block:: python

    from trees.btcaverage import RedisConverter

    from websauna.system.core.redis import get_redis
    from websauna.system.task import task
    from websauna.system.task import TransactionalTask


    @task(name="update_conversion_rates", base=TransactionalTask, bind=True)
    def update_btc_rate(self):
        request = self.request.request
        redis = get_redis(request)
        converter = RedisConverter(redis)
        converter.update()


Another example can be found in :py:mod:`websauna.system.devop.backup`.

Setting schedule
~~~~~~~~~~~~~~~~

Your project INI configuration file has a section for Celery and Celery tasks. In below we register our custom task beside the default backup task

.. code-block:: ini

    [app:main]
    # ...
    websauna.celery_config =
        {
            "broker_url": "redis://localhost:6379/3",
            "accept_content": ['json'],
            "beat_schedule": {
                # config.scan() scans a Python module
                # and picks up a celery task named test_task
                "update_conversion_rates": {
                    "task": "update_conversion_rates",
                    # Run every 30 minutes
                    "schedule": timedelta(minutes=30)
                }
            }
        }


More information
================

See

* :py:mod:`websauna.tests.demotasks`

* :py:mod:`websauna.system.devop.tasks`

* :py:mod:`websauna.system.task.tasks`

* :py:mod:`websauna.system.task.celeryloader`

* :py:mod:`websauna.system.task.celery`

Troubleshooting
===============

Inspecting task queue
---------------------

Sometimes you run to issues of not being sure if the tasks are being executed or not. First check that Celery is running, both scheduler process and worker processes. Then you can check the status of Celery queue.

Start shell or do through IPython Notebook::

    ws-shell production.ini

How many tasks queued in the default celery queue::

    from celery.task.control import inspect
    i = inspect()
    print(len(list(i.scheduled().values())[0]))

Print out Celery queue and active tasks::

    from celery.task.control import inspect
    i = inspect()
    for celery, data in i.scheduled().items():
        print("Instance {}".format(celery))
        for task in data:
            print(task)
        print("Queued: {}".format(i.scheduled()))

    print("Active: {}".format(i.active()))


Dropping task queue
-------------------

First stop worker.

Then start worker locally attacted to the terminal with --purge and it will drop all the messages::

    ws-celery production.ini -- worker --purge

Stop with CTRL+C.

Start worker again properly daemonized.
