#!/usr/bin/env python

import os
import salt.client
import salt.config
import salt.output
from glob import glob
import ruamel.yaml
import pprint

class Wheel:

    def __init__(self, config, recipe=None):
        self.logseverity = {'error':1, 'info':2, 'debug':3}
        self.config = config
        self.recipe = recipe if recipe else {}

    def log(self, msg, severity='info', level=0):
        if self.logseverity[severity] <= self.logseverity[self.config.get('logging').get('severity', 'info')]:
           print('== {}'.format(' '*level+str(msg)))

    def runner(self):
        """
        Iterates wheelhouse:jobs and trigger invidual wheels defined

        wheelhouse:
          jobs:
            <job_name>:
              recipe:
                - <wheel_name>
        """

        for job_nm in self.recipe.get('jobs', {}):
            job = self.config['jobs'][job_nm]

            self.log('Job: {}'.format(job_nm))

            for wheel_nm in job.get('wheels', {}):
                wheel = self.config['wheels'][wheel_nm]

                self.log('wheel: {}'.format(wheel_nm))
                self.run(wheel_nm, wheel)

    def run(self, fn, values):
        pass

    def client(self):
        pass

    def dictify(self, _dict):
        for k in _dict.keys():
          if isinstance(_dict[k], ruamel.yaml.comments.CommentedMap):
             _dict[k] = self.dictify(dict(_dict[k]))
          #elif isinstance(_dict[k], ruamel.yaml.comments.CommentedSeq):
             #_dict[k] = list(_dict[k])
        return _dict

    def safeMergeDict(self, x, y):
        # python3:
        # return { **self.dictify(x), **self.dictify(y) }
        x = self.dictify(x)
        y = self.dictify(y)
        z = x.copy()   # start with x's keys and values
        z.update(y)    # modifies z with y's keys and values & returns None
        return z

class WheelSalt(Wheel):

    def __init__(self, config, recipe=None):
        Wheel.__init__(self, config, recipe=recipe)
        self.salt_opts = {'state-output': 'changes', 'log-severity': 'info', 'with_grains': True, 'test': False}
        self.salt_config = {}

    def client(self):
        """
        Init salt client (salt.client.Caller)
        """
        # Salt init
        # https://docs.saltstack.com/en/latest/ref/clients/

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        default_config  = dict(ruamel.yaml.YAML().load("""\
        file_client: local
        master: localhost
        file_roots:
          base:
           - {}
        """.format('/usr/share/salt-formulas/env')))
        __opts__ = self.safeMergeDict(__opts__, default_config)
        __opts__ = self.safeMergeDict(__opts__, self.config.get('config', {}).get('salt', {}).get('minion', {}) )
        #__opts__ = self.safeMergeDict(__opts__, minion_config)
        self.salt_config = __opts__
        return salt.client.Caller(mopts=self.salt_config)

    def run(self, wheel_nm, wheel):
        """
        Process individual wheel

        wheel:
          <wheel_name>:
             state.apply:
               - test.ping
             state.sls: { <sls> }
             test.ping: []
             ...
        """

        for fn, values in wheel.items():

            states= []
            salt_c = self.client()
            os.chdir(self.salt_config.get('file_roots', {}).get('base', ['/usr/share/salt-formulas/env'])[0])

            # TODO: clean up first->after # top.sls etc..
            for f in glob("*.sls"):
                try:
                    os.remove(f)
                except OSError:
                    pass

            # implement functions
            if fn in ['state.apply', 'state.sls']:
                if isinstance(values, list):
                     states=values
                elif isinstance(values, ruamel.yaml.comments.CommentedMap) or isinstance(values, dict): # RAW SLS FILE ON VALUES
                    with open('top.sls','w') as out:
                      out.write(''.join((
                     "base:\n",
                     "  '*':\n",
                     "     - {}\n".format(wheel_nm)
                      )))
                    with open('{}.sls'.format(wheel_nm),'w') as out:
                       ruamel.yaml.dump(values, out, Dumper=ruamel.yaml.RoundTripDumper)

            pillar = { 'pillar': self.config.get('pillar', {}) }
            args   = [ ','.join(states) ]
            kwargs = self.safeMergeDict(self.salt_opts, wheel.get('config', {}).get('salt', {}).get('opts', {}))
            kwargs = self.safeMergeDict( kwargs, pillar )

            ret = salt_c.cmd(fn, *args, **kwargs)
            salt.output.display_output(
                    {'local': ret},
                    out=ret.get('out', 'highstate'),
                    opts=self.salt_config,
                    _retcode=ret.get('retcode', 0))




# For testing:
# docker run -v $PWD:/wheelhouse -ti tcpcloud/salt-formulas /bin/bash
# /wheelhouse/wheelhouse.py
if __name__ == '__main__':
    pp = pprint.PrettyPrinter(indent=2, width=80)
    config  = ruamel.yaml.YAML().load("""\
        enabled: true
        engine: salt
        image:  tcpcloud/salt-formulas
        logging:
          severity: info
        jobs:
            init:
                wheels:
                    - initdb
                logging:
                    severity: debug
            cron_data_prunning:
                wheels:
                    - minion_influxdb_config
                    - delete_data
            dummy_test:
                wheels:
                    - minion_influxdb_config
                    - dummy_direct_sls_invocation
        pillar:
            salt:
              minion:
                  config:
                    # This section is only needed if salt state ``influxdb_continuous_query.present`` is used
                    influxdb:
                      host: localhost
                      port: 8086
            influxdb:
                client:
                    enabled: true
                    server:
                      protocol: http
                      host: localhost
                      port: 8086
                      user: admin
                      password: admin
                    user:
                      1:
                        name: fluentd
                        password: password
                        enabled: true
                        admin: true
                    database:
                        1:
                            name: h2o_measurement
                            enabled: true
                            retention_policy:
                            - name: rp_db1
                              duration: 30d
                              replication: 1
                              is_default: true
                            continuous_query:
                                cq_avg_bus_passengers: >-
                                    SELECT mean("h2o_quality") INTO "h2o_measurement"."three_weeks"."average_quality" FROM "bus_data" GROUP BY time(1h)
                            query:
                                drop_h2o: >-
                                    DROP MEASUREMENT h2o_measurement
                                delete_h2o: >-
                                    DELETE FROM "h2o_measurement" WHERE type='h2o'
                    grant:
                        fluentd_h2o_measurement:
                            enabled: true
                            user: fluentd
                            database: h2o_measurement
                            privilege: all
        wheels:
            initdb:
                state.apply:
                    - influxdb.client
            delete_data:
                # Call formula state sls NS by an ID
                state.sls_id:
                    - delete_h2o
                    - influxdb.query
            minion_influxdb_config:
                state.apply:
                    /etc/salt/minion:
                        file.serialize:
                        - dataset_pillar:  salt:minion:config
                        - formatter:       yaml
                        - merge_if_exists: True
                        - makedirs: True
            dummy_direct_sls_invocation:
                state.apply:
                    make_dir:
                        file.directory:
                        - name: /var/log/influxdb
                        - makedirs: True
                        - mode: 755
                    #create_dummy_database:
                    #    influxdb_database.present:
                    #        - name: dummy1
                    #set_a_year_retention_db_metrics:
                    #    influxdb_retention_policy.present:
                    #        - name: a_year
                    #        - database: dummy1
                    #        - duration: 52w
                    #        - retention: 1
                    #        - default: false
                    #        #- host: localhost
                    #        #- port: 8086
                    #insert_dummy_data:
                    #    module.run:
                    #      influxdb.query:
                    #        - database: h2o_measurement
                    #        - query: INSERT treasures,captain_id=pirate_king value=2
                    #set_continuous_queries:
                    #    influxdb_continuous_query.present:
                    #       ...
                    #       ...

    """)
    recipe = {'jobs': ['init', 'dummy_test']}
    wheel = WheelSalt(config, recipe=recipe)
    wheel.runner()
