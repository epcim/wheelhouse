# wheelhouse

Opinionated invocation of configuration management tools for containerized workload.

## TL;DR

Uses config.mgmt. tools to take ops actions against containerized/remote apps/api's.

Wheelhouse is server-less, cli-less, local invocation of salt|chef|ansible|... controlled only
by input yaml structured metadata.

## Intro

We wrote great procedures under chef/salt/ansible/... to manage our apps. Many of them can be
executed remotely over api or as a side container interact on the same volume with the apps.

I found this code usefull worth to reuse and I reject to rewrite all the logic to go templates.
Crumble it into a bunch of yaml templates and replace higher languages back to the rigit bash scripts.

Sure if you task is to simply run `curl` do do simple api call, take a `busybox` and doit.
However if you setup users, acls, setting up the configurations or manipulate data do it proper way.

Suited not only for Kubernetes Helm Charts advertised below. Not favoriting any config.mgmt tool.
I used minimal yaml structure as config so less people can burble about it.

The structure is simple as:

    wheelhose:
      engine: [salt|chef|ansible]
      job:
        {job_name}:
          wheel:
            - {wheel_name} (like job|role|recipe|playbook name)

      pillar:
        {metadata|attributes|pillars|variables}
      wheel:
         {wheel_name}:
           {actual state|formula|module|function|recipe|cookbook}:
             {args as list/dict/value}

The jobs is a collection of individual "wheels" defined later from your favourite config.mgmt tool.
Wheels are responsible to apply `states` (in salt terminology, or `recipes` in chef world), etc...

## Reasonings:

* http://apealive.net/post/helm-charts-wheelhouse



## Usage

Quick & play sandbox:

     docker run -v $PWD:/wh -ti epcim/salt-formulas:wheelhouse-debian-stretch-salt-2017.7-formula-nightly /bin/bash
     install influxdb:
       curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
       source /etc/os-release
       echo "deb https://repos.influxdata.com/${ID,,} ${VERSION_CODENAME:- stretch} stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
       sudo apt-get update && sudo apt-get install influxdb
       influxd &
     /wh/wheelhouse.py -t

