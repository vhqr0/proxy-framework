CONFIG_FILE = 'config.json'

INBOX_URL = 'http://user:pwd@localhost:1080'
OUTBOX_URL = 'http://user:pwd@localhost:443'

RULES_DEFAULT = 'direct'
RULES_FILE = 'rules.txt'

CONNECT_RETRY = 3

WEIGHT_INITIAL = 10.0
WEIGHT_MINIMAL = 1.0
WEIGHT_MAXIMAL = 100.0
WEIGHT_INCREASE_STEP = 1.0
WEIGHT_DECREASE_STEP = 1.0

LOG_FORMAT = '%(asctime)s %(name)s %(levelname)s %(message)s'
LOG_DATEFMT = '%y-%m-%d %H:%M:%S'
