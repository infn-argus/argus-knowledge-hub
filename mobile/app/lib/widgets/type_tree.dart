import 'package:flutter/material.dart';

import '../domain/capture.dart';

/// The type a list is narrowed to, as a button that says where in the hierarchy it is ("Vacuum › Ion
/// Pump"), opening the whole tree to choose another — the web's type tree, made for a phone. A type
/// includes everything below it; [counts] are each type's own records, and the tree shows a branch's total.
class TypeFilterButton extends StatelessWidget {
  const TypeFilterButton({
    super.key,
    required this.tree,
    required this.selected,
    required this.onSelected,
    this.counts = const {},
    this.label = 'All types',
  });

  final TypeTree? tree;
  final String? selected;
  final ValueChanged<String?> onSelected;
  final Map<String, int> counts;
  final String label;

  @override
  Widget build(BuildContext context) {
    final path = tree?.path(selected) ?? const <TypeNode>[];
    return ActionChip(
      key: const Key('type-filter'),
      avatar: const Icon(Icons.account_tree_outlined, size: 18),
      label: Text(path.isEmpty ? label : path.map((t) => t.name).join(' › '),
          maxLines: 1, overflow: TextOverflow.ellipsis),
      onPressed: tree == null
          ? null
          : () async {
              final picked = await showModalBottomSheet<_Pick>(
                context: context,
                isScrollControlled: true,
                showDragHandle: true,
                builder: (_) => _TypeSheet(tree: tree!, selected: selected, counts: counts, label: label),
              );
              if (picked != null) onSelected(picked.uid);
            },
    );
  }
}

class _Pick {
  const _Pick(this.uid);
  final String? uid;
}

class _TypeSheet extends StatefulWidget {
  const _TypeSheet({required this.tree, required this.selected, required this.counts, required this.label});

  final TypeTree tree;
  final String? selected;
  final Map<String, int> counts;
  final String label;

  @override
  State<_TypeSheet> createState() => _TypeSheetState();
}

class _TypeSheetState extends State<_TypeSheet> {
  late final Set<String> _open = {for (final t in widget.tree.path(widget.selected)) t.uid};
  String _q = '';

  int _total(TypeNode t) => (widget.counts[t.uid] ?? 0) + t.children.fold(0, (n, c) => n + _total(c));

  bool _matches(TypeNode t) =>
      t.name.toLowerCase().contains(_q) || t.children.any(_matches);

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    void add(TypeNode t, int depth) {
      if (_q.isNotEmpty && !_matches(t)) return;
      final open = _q.isNotEmpty || _open.contains(t.uid);
      final n = _total(t);
      rows.add(ListTile(
        key: Key('type-${t.uid}'),
        dense: true,
        selected: t.uid == widget.selected,
        contentPadding: EdgeInsets.only(left: 8.0 + depth * 20, right: 16),
        leading: t.children.isEmpty
            ? const SizedBox(width: 24)
            : IconButton(
                visualDensity: VisualDensity.compact,
                icon: Icon(open ? Icons.expand_more : Icons.chevron_right),
                onPressed: () => setState(() => open ? _open.remove(t.uid) : _open.add(t.uid)),
              ),
        title: Text(t.name, style: t.concrete ? null : const TextStyle(fontStyle: FontStyle.italic)),
        trailing: widget.counts.isEmpty ? null : Text('$n'),
        onTap: () => Navigator.pop(context, _Pick(t.uid)),
      ));
      if (open) {
        for (final c in t.children) {
          add(c, depth + 1);
        }
      }
    }

    for (final r in widget.tree.roots) {
      add(r, 0);
    }
    return SafeArea(
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.75,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: TextField(
              key: const Key('type-search'),
              decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Find a type'),
              onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
            ),
          ),
          ListTile(
            key: const Key('type-all'),
            leading: const Icon(Icons.select_all),
            title: Text(widget.label),
            selected: widget.selected == null,
            onTap: () => Navigator.pop(context, const _Pick(null)),
          ),
          const Divider(height: 1),
          Expanded(child: ListView(children: rows)),
        ]),
      ),
    );
  }
}

/// Where a record's type sits in the hierarchy, as the web's detail pages show it: "Equipment › Vacuum ›
/// Ion Pump".
class TypeBreadcrumb extends StatelessWidget {
  const TypeBreadcrumb({super.key, required this.tree, required this.schemaUid});

  final TypeTree? tree;
  final String? schemaUid;

  @override
  Widget build(BuildContext context) {
    final path = tree?.path(schemaUid) ?? const <TypeNode>[];
    if (path.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Row(key: const Key('type-breadcrumb'), children: [
      Icon(Icons.account_tree_outlined, size: 16, color: theme.colorScheme.outline),
      const SizedBox(width: 6),
      Expanded(
        child: Text(path.map((t) => t.name).join(' › '),
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.outline)),
      ),
    ]);
  }
}
