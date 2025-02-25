# SLSP Tools
* Authors: Raphaël Rey [raphael.rey@slsp.ch](mailto:raphael.rey@slsp.ch)
* Date: 2025-02-25
* Version: alpha 1.0.0

## Description
This project is a platform providing a tool for deduplication and similarity evaluation of records.
It is useful to build training datasets for machine learning models.

## Features
- Evaluate similarity between Marc21 records
- Prepare training datasets for machine learning models

## Technologies
- Python
- Vue.js
- Django
- MongoDB
- MariaDB

## Installation
### Requirements
Several libraries are required to run the app. You can install them with the following command:
   ```bash
   pip install -r requirements.txt
   ```

### Environment variables
To use the app you need a `.env` file in the slsptools folder. It contains the django secret key
and the MongoDB database credentials. The repository contains a `.env.example` file that you can
copy and rename to `.env` and fill in the values. Normally the .env is only used in development
mode. In production, the environment variables are set on the server.

```
django_env=dev
mongodb_dedup_uri=mongodb://mongodb_dedup:<pwd>@<mongodb_server>/?authSource=records
nz_db=records
nz_db_col=nz_records
dedup_db=dedup
django_secret_key=<dev_secret_key>
django_secret_key_prod=<prod_secret_key>
maria_db_password=<maria_db_password>
```

## Configuration
The app is configured to use a MongoDB database. The database needs to be filled with records
before using the app. The app is only used to evaluate the similarity between records.

Main steps to prepare the data:
1. Select a material type and use MongoDB to build a database with an index of the existing
    records. The index covers titles and creators.
2. Analyse the local data against the NZ data to find the best matches.
3. Use the app to evaluate the similarity between the records and decide if they are
    duplicates.

Thresholds to decide if two records are similar can be set in the app. They can be adjusted to get
the best results. These thresholds are configured during the upload of the data in the database.

## Authentication
The app uses a Django authentication system. An SLSP admin can create an account for a user. The
simplest way is to create a superuser with the following command:
   ```bash
   slsptools/manage.py createsuperuser
   ```

The user can then log in the admin site and create other users if required.

## Usage
To start local server:
   ```bash
   slsptools/manage.py runserver
   ```

To deploy in production, connect on the server with SSH and run `deploy.sh` script.

## License
This project is licensed under the GNU General Public License v3 License. See the `LICENSE`
file for more details.