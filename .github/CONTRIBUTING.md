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
1. fork from `develop` branch.
2. commit to your repository.
3. marge pull request to `develop`, please wait reply from core contributors.

Before pull request
----
* Functions, do you confirm the function is easy to understand? enough documents?
* Migrations, do you confirm the migration has backward compatibility?
* Tools, do you confirm the tool is backed by realistic scenarios? check dependency?

Before issue
----
* Duplication, already raised same issues?
* Documents, already written in documents?
* Question, easily solved if you search by Google?

In Japanese
----
日本人なせいか英語で書いていたらよくわからなくなったので要約。
* コア開発者は、主に`develop`にCommit、採用するか不明な機能はBranchきって別にCommitする。
* コア開発者は、`develop`での開発が一段落したらSubVer上げて`master`にMargeする。
* コントリビュータは、`develop`よりForkして変更点を加えた後に`develop`へプルリクエストする。
* プルリクエストへのMarge可否がコア開発者より返信されます。
* コントリビュータは、プルリクエスト/イシュー作成前にご確認よろしくお願いします。

