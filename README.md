# SLSP Tools
# ABN CUG
* Authors: Raphaël Rey [raphael.rey@slsp.ch](mailto:raphael.rey@slsp.ch)
* Date: 2024-12-06
* Version: alpha 0.1.0

## Description
This project is a tool for deduplication and similarity evaluation of records. It provides
an interface to analyze the similarity between two records. It is useful to build training
datasets for machine learning models.

## Features
- Evaluate similarity between Marc21 records

## Technologies
- Python
- Vue.js
- Django
- MongoDB

## Installation
To use the app you need a `.env` file in the slsptools folder. It contains the django secret key
and the MongoDB database credentials. Here is an example of the content of the `.env` file:

```
django_secret_key=your_secret_key
mongodb_tir_uri=your_db_uri
```

## Usage
To start local server:
   ```bash
   slsptools/manage.py runserver
   ```

## License
This project is licensed under the GNU General Public License v3 License. See the `LICENSE`
file for more details.