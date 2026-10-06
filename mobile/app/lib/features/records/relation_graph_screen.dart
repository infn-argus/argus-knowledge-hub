import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';

/// A small twin of the web app's interactive relation graph (components/RelationGraph.tsx): the record
/// in the centre, what it points at on one side, what points at it on the other. Tap a neighbour to see
/// it, double-tap to make it the new centre, pinch or scroll to zoom. Built on the single-hop
/// `relations` the asset-context endpoint already returns — no separate graph API, and no attempt at the
/// web page's on-demand multi-hop expansion, which is more than a phone screen can usefully show at once.
class RelationGraphScreen extends ConsumerStatefulWidget {
  const RelationGraphScreen({super.key, required this.rootUid, required this.rootName});

  final String rootUid;
  final String rootName;

  @override
  ConsumerState<RelationGraphScreen> createState() => _RelationGraphScreenState();
}

class _RelationGraphScreenState extends ConsumerState<RelationGraphScreen> {
  late String _centerUid = widget.rootUid;
  late String _centerName = widget.rootName;
  RelationItem? _selected;

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(assetDetailProvider(_centerUid));
    return Scaffold(
      appBar: AppBar(title: Text('Relations of $_centerName'), actions: [
        IconButton(
          tooltip: 'Open this record',
          icon: const Icon(Icons.open_in_new),
          onPressed: () => context.push('/asset/$_centerUid'),
        ),
      ]),
      body: detail.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(assetDetailProvider(_centerUid))),
        data: (a) => a.relations.isEmpty
            ? const Center(child: Text('Nothing is connected to this record.'))
            : Column(children: [
                Expanded(
                  child: InteractiveViewer(
                    minScale: 0.4,
                    maxScale: 3,
                    boundaryMargin: const EdgeInsets.all(200),
                    child: _Graph(
                      centerName: a.name,
                      items: a.relations,
                      selected: _selected,
                      onTap: (r) => setState(() => _selected = _selected?.uid == r.uid ? null : r),
                      onDoubleTap: (r) => setState(() {
                        _centerUid = r.uid;
                        _centerName = r.name;
                        _selected = null;
                      }),
                    ),
                  ),
                ),
                if (_selected != null) _selectedBar(context, _selected!),
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 6),
                  child: Text('Tap to select · double-tap to centre on it', style: TextStyle(fontSize: 12, color: Colors.grey)),
                ),
              ]),
      ),
    );
  }

  Widget _selectedBar(BuildContext context, RelationItem r) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: ListTile(
        dense: true,
        leading: Icon(r.direction == 'out' ? Icons.call_made : Icons.call_received),
        title: Text(r.name),
        subtitle: Text('${r.relation.replaceAll('_', ' ')} · ${r.type}'),
        trailing: Wrap(spacing: 4, children: [
          TextButton(onPressed: () => context.push('/asset/${r.uid}'), child: const Text('Open')),
          TextButton(
            onPressed: () => setState(() {
              _centerUid = r.uid;
              _centerName = r.name;
              _selected = null;
            }),
            child: const Text('Centre here'),
          ),
        ]),
      ),
    );
  }
}

/// A radial layout: outbound neighbours to the right, inbound to the left, grouped by relation type so a
/// dozen "contains" edges read as one arc rather than twelve overlapping lines.
class _Graph extends StatelessWidget {
  const _Graph({required this.centerName, required this.items, required this.onTap, required this.onDoubleTap, this.selected});

  final String centerName;
  final List<RelationItem> items;
  final RelationItem? selected;
  final void Function(RelationItem) onTap;
  final void Function(RelationItem) onDoubleTap;

  static const _radius = 170.0;
  static const _nodeR = 46.0;

  @override
  Widget build(BuildContext context) {
    final out = items.where((r) => r.direction == 'out').toList();
    final inb = items.where((r) => r.direction == 'in').toList();
    final size = Size(_radius * 2 + _nodeR * 2 + 40, math.max(math.max(out.length, inb.length), 1) * 72.0 + 160);
    final center = Offset(size.width / 2, size.height / 2);
    final outPositions = _arc(center, out.length, right: true);
    final inPositions = _arc(center, inb.length, right: false);

    return SizedBox(
      width: size.width,
      height: size.height,
      child: Stack(children: [
        CustomPaint(
          size: size,
          painter: _EdgePainter(center: center, out: outPositions, inb: inPositions, scheme: Theme.of(context).colorScheme),
        ),
        _node(context, center, centerName, isCenter: true),
        for (final (i, r) in out.indexed) _relationNode(context, outPositions[i], r),
        for (final (i, r) in inb.indexed) _relationNode(context, inPositions[i], r),
      ]),
    );
  }

  List<Offset> _arc(Offset center, int count, {required bool right}) {
    if (count == 0) return const [];
    final span = math.min(math.pi * 0.86, 0.5 + count * 0.3);
    final start = -span / 2;
    return [
      for (var i = 0; i < count; i++)
        center +
            Offset.fromDirection(
              (right ? 0 : math.pi) + (count == 1 ? 0 : start + span * i / (count - 1)),
              _radius,
            ),
    ];
  }

  Widget _relationNode(BuildContext context, Offset at, RelationItem r) {
    final isSelected = selected?.uid == r.uid;
    final scheme = Theme.of(context).colorScheme;
    return Positioned(
      left: at.dx - _nodeR,
      top: at.dy - _nodeR,
      width: _nodeR * 2,
      height: _nodeR * 2,
      child: GestureDetector(
        onTap: () => onTap(r),
        onDoubleTap: () => onDoubleTap(r),
        child: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isSelected ? scheme.primaryContainer : scheme.surface,
            border: Border.all(color: r.direction == 'out' ? scheme.tertiary : scheme.secondary, width: isSelected ? 3 : 2),
            boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 3, offset: Offset(0, 1))],
          ),
          padding: const EdgeInsets.all(6),
          child: Center(
            child: Text(r.name, maxLines: 3, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall),
          ),
        ),
      ),
    );
  }

  Widget _node(BuildContext context, Offset at, String label, {bool isCenter = false}) {
    final scheme = Theme.of(context).colorScheme;
    return Positioned(
      left: at.dx - _nodeR,
      top: at.dy - _nodeR,
      width: _nodeR * 2,
      height: _nodeR * 2,
      child: Container(
        decoration: BoxDecoration(shape: BoxShape.circle, color: scheme.primary,
            boxShadow: const [BoxShadow(color: Colors.black38, blurRadius: 4, offset: Offset(0, 2))]),
        padding: const EdgeInsets.all(8),
        child: Center(
          child: Text(label, maxLines: 3, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onPrimary, fontWeight: FontWeight.bold)),
        ),
      ),
    );
  }
}

class _EdgePainter extends CustomPainter {
  _EdgePainter({required this.center, required this.out, required this.inb, required this.scheme});

  final Offset center;
  final List<Offset> out;
  final List<Offset> inb;
  final ColorScheme scheme;

  @override
  void paint(Canvas canvas, Size size) {
    final outPaint = Paint()..color = scheme.tertiary..strokeWidth = 1.6;
    final inPaint = Paint()..color = scheme.secondary..strokeWidth = 1.6;
    for (final p in out) {
      _arrow(canvas, center, p, outPaint);
    }
    for (final p in inb) {
      _arrow(canvas, p, center, inPaint);
    }
  }

  void _arrow(Canvas canvas, Offset from, Offset to, Paint paint) {
    final dir = (to - from);
    final len = dir.distance;
    if (len == 0) return;
    final unit = dir / len;
    final start = from + unit * 46;
    final end = to - unit * 46;
    canvas.drawLine(start, end, paint);
    final back = -unit;
    final perp = Offset(-unit.dy, unit.dx);
    final head = end + back * 10;
    final p1 = head + perp * 5;
    final p2 = head - perp * 5;
    canvas.drawPath(Path()..moveTo(end.dx, end.dy)..lineTo(p1.dx, p1.dy)..lineTo(p2.dx, p2.dy)..close(),
        Paint()..color = paint.color);
  }

  @override
  bool shouldRepaint(covariant _EdgePainter oldDelegate) =>
      oldDelegate.center != center || oldDelegate.out != out || oldDelegate.inb != inb;
}
