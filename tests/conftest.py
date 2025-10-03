import os
import sys
from pathlib import Path
# Ensure project root is on sys.path for imports like 'backend.*'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import sqlite3
import pytest

TEST_DB = Path("./tests/test_demo.db")


def setup_demo_db():
    if TEST_DB.exists():
        TEST_DB.unlink()
    conn = sqlite3.connect(TEST_DB)
    cur = conn.cursor()
    # Schema variation 1
    cur.executescript(
        """
        CREATE TABLE departments (
            dept_id INTEGER PRIMARY KEY,
            dept_name TEXT,
            manager_id INTEGER
        );
        CREATE TABLE employees (
            emp_id INTEGER PRIMARY KEY,
            full_name TEXT,
            dept_id INTEGER,
            position TEXT,
            annual_salary REAL,
            join_date TEXT,
            office_location TEXT,
            FOREIGN KEY(dept_id) REFERENCES departments(dept_id)
        );
        INSERT INTO departments (dept_id, dept_name, manager_id) VALUES
            (1, 'Engineering', 100),
            (2, 'HR', 101);
        INSERT INTO employees (emp_id, full_name, dept_id, position, annual_salary, join_date, office_location) VALUES
            (10, 'Alice Smith', 1, 'Engineer', 120000, '2023-02-10', 'NY'),
            (11, 'Bob Jones', 1, 'Sr Engineer', 150000, '2024-01-20', 'NY'),
            (12, 'Carol White', 2, 'HR Manager', 110000, '2022-08-01', 'SF');
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture(scope="session")
def demo_db_url():
    setup_demo_db()
    return f"sqlite:///{TEST_DB}"
