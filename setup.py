import os.path

from setuptools import setup

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, 'README.md')) as f:
    long_description = f.read()

setup(
    name='redbucket',
    use_scm_version=True,
    license="MIT License",
    description="Python rate limiting library using Redis for shared state.",
    author="Nicholas Gaya",
    author_email="nicholasgaya+pypi@gmail.com",
    url="https://github.com/nickgaya/redbucket",
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=["redbucket"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    setup_requires=[
        'setuptools_scm',
    ],
    python_requires='>=3.6,<4',
)