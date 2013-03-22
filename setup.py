from setuptools import setup, find_packages

setup(
    name='django-repomgmt',
    version='0.1.1',
    description='APT repo management, buildd, etc.',
    author='Soren Hansen',
    author_email='sorhanse@cisco.com',
    url='http://github.com/sorenh/python-django-repomgmt',
    packages=find_packages(),
    include_package_data=True,
    license='Apache 2.0',
    keywords='django apt repository buildd',
    install_requires=[
        'django',
    ],
    test_suite='tests.main',
    classifiers=[
      'Development Status :: 2 - Pre-Alpha',
      'Environment :: Web Environment',
      'Framework :: Django',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: Apache Software License',
      'Operating System :: POSIX :: Linux',
      'Programming Language :: Python',
      'Topic :: Software Development',
      'Topic :: System :: Archiving :: Packaging'
     ]
)
