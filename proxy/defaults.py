CONFIG_FILE = 'config.json'

INBOX_URL = 'http://localhost:1080'
OUTBOX_URL = 'http://localhost:443'
BLOCK_OUTBOX_URL = 'null://'
DIRECT_OUTBOX_URL = 'tcp://'

TLS_INBOX_CERT_FILE = 'cert.pem'
TLS_INBOX_KEY_FILE = 'key.pem'
TLS_INBOX_KEY_PWD = ''
TLS_OUTBOX_CERT_FILE = 'cert.pem'
TLS_OUTBOX_HOST = 'localhost'

WS_OUTBOX_PATH = '/'
WS_OUTBOX_HOST = 'localhost'

RULES_DEFAULT = 'direct'
RULES_FILE = 'rules.txt'

CONNECT_RETRY = 3

WEIGHT_INITIAL = 10.0
WEIGHT_MINIMAL = 1.0
WEIGHT_MAXIMAL = 100.0
WEIGHT_INCREASE_STEP = 1.0
WEIGHT_DECREASE_STEP = 1.0

STREAM_BUFSIZE = 2**22  # 4MB
STREAM_TCP_BUFSIZE = 2**12  # 4KB

LOG_FORMAT = '%(asctime)s %(name)s %(levelname)s %(message)s'
LOG_DATE_FORMAT = '%y-%m-%d %H:%M:%S'
