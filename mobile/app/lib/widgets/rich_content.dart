import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' show parse;

/// Imported text, rendered: a document revision's body, or a long "text"-type attribute (ARGUS Knowledge
/// Hub's `description` fields, among others). The source is Markdown for anything written or converted
/// here, but a value that came in through Jira or Confluence and was never converted is sometimes raw HTML
/// instead — `<div class="created-with-ak-editor">…</div>` is exactly what a Jira custom field holds.
/// [htmlToMarkdown] turns that into Markdown first, so one renderer (flutter_markdown_plus) handles both —
/// a dedicated HTML-widget package pulled in an incompatible `html`/`csslib` release that would not even
/// compile, and there is no reason to carry two rendering engines for text this simple (block tags,
/// bold/italic, lists, links — no embedded styling worth keeping).
///
/// [codeLink] turns an inline code span that names a record (`SPARC:ELM:SBNQUA01`) into a link to its
/// screen, opened with [onLink]; without them links inside the text are informational only.
class RichContent extends StatelessWidget {
  const RichContent(this.text, {super.key, this.style, this.codeLink = const {}, this.onLink, this.selectable = true});

  final String text;
  final TextStyle? style;
  final Map<String, String> codeLink;
  final void Function(String path)? onLink;
  /// Selectable text does not pass taps to links: text with links goes in a SelectionArea instead.
  final bool selectable;

  static final _code = RegExp(r'(?<![`\[])`([^`\n]+)`(?!`)');

  static final _htmlTag = RegExp(r'<(p|div|span|table|tr|td|th|ul|ol|li|br|b|i|strong|em|h[1-6])[\s>/]', caseSensitive: false);

  @override
  Widget build(BuildContext context) {
    if (text.trim().isEmpty) return const SizedBox.shrink();
    var markdown = _htmlTag.hasMatch(text) ? htmlToMarkdown(text) : text;
    if (codeLink.isNotEmpty) {
      markdown = markdown.replaceAllMapped(_code, (m) {
        final to = codeLink[m[1]!.trim()];
        return to == null ? m[0]! : '[${m[0]}](argus:$to)';
      });
    }
    final body = Theme.of(context).textTheme.bodyMedium?.merge(style) ?? style;
    return MarkdownBody(
      data: markdown,
      selectable: selectable,
      styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(p: body),
      onTapLink: (text, href, title) {
        if (href != null && href.startsWith('argus:')) onLink?.call(href.substring('argus:'.length));
      },
    );
  }
}

const _block = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'tr', 'table', 'blockquote'};

/// A pragmatic HTML → Markdown conversion for the shapes imported content actually takes (a Jira custom
/// field, a stray Confluence macro): paragraphs, bold/italic, lists, links, line breaks, simple tables.
/// Not a general HTML renderer — markup it does not recognise is dropped to its text content, which is
/// still better than showing someone the tags.
String htmlToMarkdown(String html) {
  final doc = parse(html);
  final buffer = StringBuffer();
  _walk(doc.body ?? doc.documentElement, buffer);
  return buffer.toString().replaceAll(RegExp(r'\n{3,}'), '\n\n').trim();
}

void _walk(dom.Node? node, StringBuffer out) {
  if (node == null) return;
  if (node is dom.Text) {
    out.write(node.text.replaceAll(RegExp(r'\s+'), ' '));
    return;
  }
  if (node is! dom.Element) return;
  final tag = node.localName ?? '';
  switch (tag) {
    case 'br':
      out.write('\n');
      return;
    case 'h1':
    case 'h2':
    case 'h3':
    case 'h4':
    case 'h5':
    case 'h6':
      out.write('\n${'#' * int.parse(tag.substring(1))} ');
      for (final c in node.nodes) {
        _walk(c, out);
      }
      out.write('\n\n');
      return;
    case 'li':
      final ordered = node.parent?.localName == 'ol';
      out.write(ordered ? '\n1. ' : '\n- ');
      for (final c in node.nodes) {
        _walk(c, out);
      }
      return;
    case 'b':
    case 'strong':
      out.write('**');
      for (final c in node.nodes) {
        _walk(c, out);
      }
      out.write('**');
      return;
    case 'i':
    case 'em':
      out.write('*');
      for (final c in node.nodes) {
        _walk(c, out);
      }
      out.write('*');
      return;
    case 'a':
      final href = node.attributes['href'];
      final label = node.text.trim();
      if (href != null && label.isNotEmpty) {
        out.write('[$label]($href)');
      } else {
        for (final c in node.nodes) {
          _walk(c, out);
        }
      }
      return;
    case 'td':
    case 'th':
      out.write('| ');
      for (final c in node.nodes) {
        _walk(c, out);
      }
      out.write(' ');
      return;
    case 'script':
    case 'style':
      return; // never rendered, never executed either way — Flutter has no script engine
    default:
      if (_block.contains(tag)) out.write('\n');
      for (final c in node.nodes) {
        _walk(c, out);
      }
      if (_block.contains(tag)) out.write('\n');
  }
}
