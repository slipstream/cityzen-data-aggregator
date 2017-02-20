
# Graphite configuration

graphite_address = '127.0.0.1'
graphite_port = 2003


# Owlet configuration

name = 'owlet'
endpoint = ''
username = ''
password = ''
client_cert = 'owlet.pem'
verify_cert = True

app_names = {'SYS01': 'dimmable',
             'SYS02': 'metering'}

metrics = {'FDL': {'name': 'dim_level_percent'},
           'FEC': {'name': 'energy_consumption_kwh'}}

cities = {'GVA': 'geneva'}

districts = {'123': 'servette'}

streets = {'4567': 'rue_de_la_servette',
           '8910': 'rue_liotard'}

devices = ['CH_GVA_1234567_ROAD', 'CH_GVA_1238910_PARK']

