Development Guideline
====
We write this document to declare how to develop this repository.
We and contributors will follow this guideline when merging changes and adding new functions.
We think specifications should be backed by technical curiosity.

Development process (core contributors)
----
If we develop required functions, commit to `develop` branch, and push to `master` after a section complete.
or if we develop experimental or can be abolished functions,
we checkout new branch and commit to `develop` after complete.

Development process (external contributors)
----
simple
1. fork from `develop` branch.
2. commit to your repository.
3. marge pull request, please wait reply from core contributors.

Before pull request
----
* Functions, do you confirm the function is easy to understand? enough documents?
* Migrations, do you confirm the migration has backward compatibility?
* Tools, do you confirm the tool is backed by realistic scenarios? check dependency?
