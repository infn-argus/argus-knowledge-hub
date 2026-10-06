import 'package:argus_field/widgets/rich_content.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // The exact shape a Jira custom field holds (asset-model-revision: imported "description" attributes
  // are sometimes raw HTML from Atlassian's editor, never converted to Markdown at import time).
  test('a Jira custom field\'s HTML becomes readable Markdown, not literal tags', () {
    const html = '<div class="created-with-ak-editor content-wrapper"><p>Nome precedente: '
        'FI1-B-CAM-BAS-001</p></div>';
    final md = htmlToMarkdown(html);
    expect(md, isNot(contains('<div')));
    expect(md, isNot(contains('class=')));
    expect(md, contains('Nome precedente: FI1-B-CAM-BAS-001'));
  });

  test('bold, italic and links survive the conversion', () {
    final md = htmlToMarkdown('<p>Check the <strong>interlock</strong> before <em>any</em> work. '
        '<a href="https://example.org/x">Procedure</a>.</p>');
    expect(md, contains('**interlock**'));
    expect(md, contains('*any*'));
    expect(md, contains('[Procedure](https://example.org/x)'));
  });

  test('a list becomes Markdown list items, one per line', () {
    final md = htmlToMarkdown('<ul><li>Isolate</li><li>Replace</li><li>Bake</li></ul>');
    expect(md.split('\n').where((l) => l.trim().startsWith('-')).length, 3);
    expect(md, contains('Isolate'));
  });

  test('a <br> becomes a line break, a <script> is dropped (and could not run here regardless)', () {
    final md = htmlToMarkdown('<p>Line one<br>Line two</p><script>alert(1)</script>');
    expect(md.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).toList(), ['Line one', 'Line two']);
    expect(md, isNot(contains('alert')));
  });

  test('plain Markdown with no HTML in it passes straight through', () {
    expect(htmlToMarkdown('**bold** and *italic*'), contains('**bold** and *italic*'));
  });
}
