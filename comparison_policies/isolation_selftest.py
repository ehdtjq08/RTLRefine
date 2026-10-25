"""Infrastructure test only: checks private-file/key/network isolation, no novelty."""
import os
from pathlib import Path
import socket


def rank(public,views,seed):
    assert not Path('/home/hands/Nebius/.env').exists()
    assert not Path('/home/hands/Nebius/results').exists()
    assert not os.environ.get('NEBIUS_API_KEY')
    connection=socket.socket();connection.settimeout(.2)
    try:
        connection.connect(('1.1.1.1',443))
    except OSError:
        pass
    else:
        raise AssertionError('Network should be unavailable')
    finally:connection.close()
    return public['orders']['heuristic_order']
