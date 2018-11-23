Markdown Sample
=======================


サンプルドキュメント日本語版
-----------------------

これはLOGGiXプロジェクトが[Markdown: Basics][2]と[PHP Markdown: Concepts][4]のMarkdownシンタックス解説を元に作成した日本語版サンプルです。
LOGGiXのVARS機能では、コンテンツに利用するテキストファイルの拡張子を`.text`とすることでMarkdownレンダリングされるようになっています。
このドキュメントはすべてMarkdownの書式に従って書かれたテキストファイルです。 このテキストファイル本体はこちらにありますので参考にしてください。(↓)

[markdown-sample.text](http://tkns.homelinux.net/modules/manual/ja/data/markdown-sample.text)

(文字コードはUTF-8、改行コードはLFです)


### 引用ブロック ###

> これは引用ブロックです。
> 
> これは引用ブロックの第2パラグラフです。
>
> ## これは引用ブロック内のH2です。

### 強調 ###

これは *強調* です。
これも _強調_ です。

 **より強い強調** には前後にアスタリスクを二つ使います。
またあるいは、 __二つのアンダースコアを使って__ も同様の表現が可能です。

### リスト ###

番号なしリストはアスタリスク、プラス記号、ハイフン(マイナス記号)を使って表現します。(*, +, と -)
記号の後にはスペースを1つ以上入れます。

(アスタリスクで記述)

*   モツァレラチーズ
*   パスタ
*   ワイン

(プラス記号で記述)

+   モツァレラチーズ
+   パスタ
+   ワイン

(ハイフン(マイナス記号)で記述)

-   モツァレラチーズ
-   パスタ
-   ワイン

番号付きリストは数字とピリオドの後にスペースを1つ以上入れて記述します。

1.   モツァレラチーズ
2.   パスタ
3.   ワイン

### Table ###

| URI     | Method |  Params | Info |
|---------|--------|---------|------|
| /hello  |  ??    | iiyo    | what |
| /world  |  !!    | koiyo   | where|


### リンク ###

Markdownは、「インライン」と「リファレンス」という二つのリンクスタイルをサポートします。

「インライン」スタイルは[ ]でかこったリンク名の後に( )でURIを囲って記述します。
URIの後に""でテキストを囲ればタイトルとして表現出来ます。

これはサンプルです。→ [W3C](http://www.w3.org/ "W3Cのトップページ").

「リファレンス」スタイルは、名前と番号を使ってページのどこかに定義したリンクを参照出来ます。

例：Markdownのページ(Perl版)はこちらの[Daring Fireball: Markdown][1]で、PHP移植版の配布元はこちらの[PHP Markdown][3]です。


[1]: http://daringfireball.net/projects/markdown/  "Daring Fireball: Markdown"
[2]: http://daringfireball.net/projects/markdown/basics "Markdown: Basics"
[3]: http://www.michelf.com/projects/php-markdown/  "PHP Markdown"
[4]: http://www.michelf.com/projects/php-markdown/concepts/  "PHP Markdown: Concepts"

### 自動リンク ###

単純に&lt;&gt;でURIを囲むことで自動リンクにすることも出来ます。

例：<http://www.w3.org>

### 画像 ###

「インライン」スタイル：
![Loggix](http://tkns.homelinux.net/theme/images/loggix-logo.png "Loggix")

「リファレンス」スタイル：
![Loggix][loggix_icon]

[loggix_icon]: http://tkns.homelinux.net/theme/images/loggix-logo.png "Loggix"

### コード ###

コード部分はバックスラッシュ(`)で囲って表現します。

例：絶対に `<blink>` タグなどは使ってはいけません。

スペース4つかタブコード1つでインデント(字下げ)することによって、
整形済みテキストブロックとして表現出来ます。

例：もしあなたの文書を XHTML 1.0 Strictで記述するなら、引用ブロックには
このようにパラグラフタグを入れなればいけません：

    <blockquote>
        <p>For example.</p>
    </blockquote>

### HTMLとの共存 ###

Markdownを使うにはHTMLの知識は必要ありませんが、MarkdownはHTMLとの共存も可能です。
もしあなたがHTMLの知識を持っていれば、Markdownでサポートされていない表現をHTMLを使うことで表現出来ます。
例えば&lt;sup&gt;タグなどはMarkdownではサポートされていませんが、以下のような日付の「st」部分を直接&lt;sup&gt;タグで
囲むことによってこのように表現出来ます。(↓)

例：April 1<sup>st</sup>
