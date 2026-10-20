.. A 7-character "=" underline (the length of "Modules") is treated as a
   merge-conflict separator by ``git diff --check`` / ``check-merge-conflict``;
   keep this underline longer than the title to avoid the false positive.

Modules
=========

An overview of the modules that make up ``fastui_admin``.
The API reference below is generated automatically from the source docstrings.

Admin app (``fastui_admin.base``)
---------------------------------

Admin application, mounting and routing.

.. automodule:: fastui_admin.base

Views (``fastui_admin.views``)
------------------------------

View hierarchy and CRUD endpoints.

.. automodule:: fastui_admin.views

Layout (``fastui_admin.layout``)
--------------------------------

Page shell, navbar and footer.

.. automodule:: fastui_admin.layout

Utilities (``fastui_admin.utils``)
----------------------------------

Dependency-free helpers and cross-module protocols.

.. automodule:: fastui_admin.utils
