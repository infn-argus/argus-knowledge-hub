import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/providers.dart';

/// A record of another workspace (a scanned label, a notification, a ticket assigned elsewhere) is opened
/// there: the app moves to that workspace first, and says so. A workspace the person cannot open is left
/// alone, and the record says it was not found.
class InWorkspace extends ConsumerStatefulWidget {
  const InWorkspace({super.key, required this.workspaceId, required this.child});

  final String? workspaceId;
  final Widget Function() child;

  @override
  ConsumerState<InWorkspace> createState() => _InWorkspaceState();
}

class _InWorkspaceState extends ConsumerState<InWorkspace> {
  late bool _moving = _elsewhere;

  bool get _elsewhere {
    final ws = widget.workspaceId;
    return ws != null && ws.isNotEmpty && ws != ref.read(workspaceIdProvider);
  }

  @override
  void initState() {
    super.initState();
    if (_moving) WidgetsBinding.instance.addPostFrameCallback((_) => _move());
  }

  Future<void> _move() async {
    try {
      final all = await ref.read(myWorkspacesProvider.future);
      final target = all.where((w) => w.id == widget.workspaceId).firstOrNull;
      if (target != null) {
        await ref.read(sessionProvider.notifier).chooseWorkspace(target);
        if (mounted) {
          ScaffoldMessenger.maybeOf(context)
              ?.showSnackBar(SnackBar(content: Text('Now in the workspace ${target.name}')));
        }
      }
    } catch (_) {
      // the record is opened where the app is; it says if it is not there
    }
    if (mounted) setState(() => _moving = false);
  }

  @override
  Widget build(BuildContext context) =>
      _moving ? const Scaffold(body: Center(child: CircularProgressIndicator())) : widget.child();
}
