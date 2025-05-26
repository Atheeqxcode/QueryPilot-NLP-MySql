from setuptools import setup, find_packages

setup(
    name="querypilot-flask-app",
    version="1.0.0",
    description="NLP-powered SQL generator and Flask web app for QueryPilot",
    author="Your Name",
    packages=find_packages(),
    py_modules=["app", "execute_query", "generate_sql_query"],
    include_package_data=True,
    install_requires=[
        "flask",
        "pandas",
        "requests",
        "python-dotenv"
    ],
    entry_points={
        "console_scripts": [
            "run-app=app:app"
        ]
    },
)
