## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- [poetry](https://python-poetry.org/) 

### Install Poetry

If you don't have poetry installed, you can install it using the following command:

```bash
pip install poetry
```

#### Install 
```bash
poetry install
```

#### Run 

```bash
poetry run uvicorn API:app --reload --workers 2
```
