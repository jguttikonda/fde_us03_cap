"""Start the mock PostgreSQL (Docker) and load the FX123 data. The container keeps running.

    python aog_coordinator/setup_db.py          # start and load
    python aog_coordinator/setup_db.py --down   # stop and remove
"""

import sys

from database import DockerPostgres, load_mock_data

if __name__ == "__main__":
    pg = DockerPostgres()
    if "--down" in sys.argv:
        pg.cleanup()
        print("PostgreSQL container removed.")
    else:
        uri = pg.start()
        load_mock_data(uri)
        print(f"PostgreSQL ready. AOG_DATABASE_URL={uri}")
