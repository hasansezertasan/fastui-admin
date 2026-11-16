Usage
=====

As a library
------------

Look up the installed distribution version:

.. literalinclude:: examples/version_lookup.py
   :language: python
   :caption: examples/version_lookup.py

For short interactive snippets embedded in prose, the ``docs-doctest`` task
executes ``>>>`` blocks too:

.. doctest::

   >>> from importlib.metadata import version
   >>> version("fastui-admin") != ""
   True
