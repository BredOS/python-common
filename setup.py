from setuptools import setup, find_packages

setup(
    name="bredos",
    version="1.0",
    packages=find_packages(),
    install_requires=["pyrunning", "pysetting", "pyalpm"],
    description="Common python functions used in BredOS applications",
    author="Panda",
    author_email="panda@bredos.org",
    url="https://github.com/BredOS/python-common",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.11",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Natural Language :: English",
    ],
    project_urls={
        "Source": "https://github.com/BredOS/python-common",
        "Issues": "https://github.com/BredOS/python-common/issues",
    },
    python_requires=">=3.11",
)
