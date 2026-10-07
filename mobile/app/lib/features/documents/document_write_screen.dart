import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
import '../../widgets/common.dart';
import '../../widgets/rich_content.dart';

/// Writing a document's text in Markdown, previewed as it will read. Without [documentUid] it writes a new
/// document — its first revision, a draft — optionally describing the record [assetUid]. With it, it edits
/// the open draft [revisionUid]: only a draft is edited; a revision in review or approved is decided, not
/// rewritten, and a published one is followed by a new revision instead.
class DocumentWriteScreen extends ConsumerStatefulWidget {
  const DocumentWriteScreen({super.key, this.documentUid, this.revisionUid, this.assetUid});

  final String? documentUid;
  final String? revisionUid;
  final String? assetUid;

  bool get isNew => documentUid == null;

  @override
  ConsumerState<DocumentWriteScreen> createState() => _DocumentWriteScreenState();
}

class _DocumentWriteScreenState extends ConsumerState<DocumentWriteScreen> {
  final _title = TextEditingController();
  TextEditingController? _body;
  String? _type;
  bool _preview = false;
  bool _saving = false;
  String? _error;
  late final String _newUid = const Uuid().v4();

  @override
  void dispose() {
    _title.dispose();
    _body?.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final body = _body!.text;
    if (widget.isNew && _title.text.trim().isEmpty) {
      setState(() => _error = 'Give the document a title.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final repo = ref.read(documentRepositoryProvider);
    try {
      if (widget.isNew) {
        final uid = await repo.create(
            uid: _newUid, title: _title.text.trim(), documentTypeUid: _type, body: body, assetUid: widget.assetUid);
        ref.invalidate(documentListProvider);
        if (widget.assetUid != null) ref.invalidate(assetDetailProvider(widget.assetUid!));
        if (mounted) context.pushReplacement('/document/$uid');
      } else {
        await repo.updateDraft(widget.documentUid!, widget.revisionUid!, body: body);
        ref.invalidate(documentRevisionsProvider(widget.documentUid!));
        if (mounted) context.pop();
      }
    } on Problem catch (p) {
      setState(() => _error = p.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.isNew) {
      _body ??= TextEditingController();
      return _scaffold(context, 'New document');
    }
    final revs = ref.watch(documentRevisionsProvider(widget.documentUid!));
    return revs.when(
      loading: () => Scaffold(appBar: AppBar(), body: const Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(
          appBar: AppBar(),
          body: ProblemView(e, onRetry: () => ref.invalidate(documentRevisionsProvider(widget.documentUid!)))),
      data: (all) {
        final rev = all.where((r) => r.uid == widget.revisionUid).firstOrNull;
        if (rev == null || rev.state != 'draft') {
          return Scaffold(
            appBar: AppBar(),
            body: const NoticeBar(icon: Icons.lock_outline, text: 'Only a draft revision can be edited.'),
          );
        }
        _body ??= TextEditingController(text: rev.body ?? '');
        return _scaffold(context, 'Edit draft · rev. ${rev.number}');
      },
    );
  }

  Widget _scaffold(BuildContext context, String title) {
    final types = widget.isNew ? (ref.watch(documentTypesProvider).value ?? const []) : const [];
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(key: const Key('doc-write-list'), padding: const EdgeInsets.all(16), children: [
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: NoticeBar(icon: Icons.error_outline, text: _error!, severe: true),
          ),
        if (widget.isNew) ...[
          TextField(
            key: const Key('doc-write-title'),
            controller: _title,
            decoration: const InputDecoration(labelText: 'Title *'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            key: const Key('doc-write-type'),
            initialValue: _type,
            decoration: const InputDecoration(labelText: 'Type'),
            items: [
              const DropdownMenuItem(value: null, child: Text('—')),
              for (final t in types) DropdownMenuItem(value: t.uid, child: Text(t.name)),
            ],
            onChanged: (v) => setState(() => _type = v),
          ),
          if (widget.assetUid != null)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('It will describe the record it was written from.'),
            ),
          const SizedBox(height: 12),
        ],
        Align(
          alignment: Alignment.centerLeft,
          child: SegmentedButton<bool>(
            key: const Key('doc-write-mode'),
            segments: const [
              ButtonSegment(value: false, icon: Icon(Icons.edit), label: Text('Write')),
              ButtonSegment(value: true, icon: Icon(Icons.visibility_outlined), label: Text('Preview')),
            ],
            selected: {_preview},
            onSelectionChanged: (s) => setState(() => _preview = s.first),
          ),
        ),
        const SizedBox(height: 8),
        if (_preview)
          Container(
            key: const Key('doc-write-preview'),
            constraints: const BoxConstraints(minHeight: 200),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
                border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                borderRadius: BorderRadius.circular(4)),
            child: _body!.text.trim().isEmpty ? const Text('Nothing written yet.') : RichContent(_body!.text),
          )
        else
          TextField(
            key: const Key('doc-write-body'),
            controller: _body,
            minLines: 12,
            maxLines: null,
            keyboardType: TextInputType.multiline,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: '# Heading\n\nSteps, notes… in Markdown',
              alignLabelWithHint: true,
            ),
          ),
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('doc-write-save'),
          onPressed: _saving ? null : _save,
          child: _saving
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : Text(widget.isNew ? 'Save as draft' : 'Save draft'),
        ),
      ]),
    );
  }
}
