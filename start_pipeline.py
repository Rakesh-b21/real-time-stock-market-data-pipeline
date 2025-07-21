import subprocess
import sys
import os
import signal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

PRODUCER_CMD = [sys.executable, '-m', 'producer.producer']
CONSUMER_CMD = [sys.executable, '-m', 'consumer.consumer']

processes = []

def start_process(cmd, name):
    logging.info(f'Starting {name}...')
    return subprocess.Popen(cmd)

def shutdown(signum, frame):
    logging.info('Shutting down pipeline...')
    for p in processes:
        p.terminate()
    for p in processes:
        p.wait()
    logging.info('All processes terminated.')
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        processes.append(start_process(PRODUCER_CMD, 'Producer'))
        processes.append(start_process(CONSUMER_CMD, 'Consumer'))
        for p in processes:
            p.wait()
    except Exception as e:
        logging.error(f'Error starting pipeline: {e}')
        shutdown(None, None) 