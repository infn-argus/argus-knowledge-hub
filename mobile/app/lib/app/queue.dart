import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../core/problem.dart';
import '../data/command_queue.dart';
import '../domain/capture.dart';
import 'providers.dart';

/// The pending-command queue (flutter-app-design §5.2, §5.3; revision §24.4).
///
/// Every change the person makes goes through here: it is kept on the device, encrypted, then sent
/// in dependency order. A change is only a fact once the server has accepted it. Until then its
/// author sees it as pending and nobody else sees it at all.
class QueueController extends AsyncNotifier<List<PendingCommand>> {
  CommandStore get _store => CommandStore(ref.read(localStoreProvider));
  bool _syncing = false;

  @override
  Future<List<PendingCommand>> build() => _store.load();

  List<PendingCommand> get _list => state.value ?? const [];

  /// Every command on the device, in the order they were made.
  List<PendingCommand> get commands => List.unmodifiable(_list);

  void _publish() => state = AsyncData([..._list]);

  /// Keep a command (and its attachments) on the device. Returns it, still `queued`.
  Future<PendingCommand> enqueue({
    required String kind,
    required String label,
    required Map<String, Object?> payload,
    String? key,
    String? target,
    String? seenVersion,
    List<(AttachmentRef, Uint8List)> attachments = const [],
    List<String> dependsOn = const [],
  }) async {
    final session = ref.read(sessionProvider).value;
    if (session?.workspaceId == null) throw Problem(ProblemCode.unauthenticated, 'Sign in first.');
    await future; // loaded
    final id = newCommandId();
    final c = PendingCommand(
      id: id,
      key: key ?? '$kind:$id',
      kind: kind,
      workspaceId: session!.workspaceId!,
      label: label,
      payload: payload,
      target: target,
      seenVersion: seenVersion,
      attachments: [for (final a in attachments) a.$1],
      dependsOn: dependsOn,
      createdAt: DateTime.now(),
      serverOffset: ref.read(reachabilityProvider).serverOffset,
    );
    for (final (att, bytes) in attachments) {
      await _store.saveBlob(att.localId, bytes);
    }
    await _store.save(c);
    state = AsyncData([..._list, c]);
    return c;
  }

  /// A photo as the attachment of an upload command.
  static (AttachmentRef, Uint8List) photo(PickedPhoto p) =>
      (AttachmentRef(localId: const Uuid().v4(), name: p.name, mimeType: p.mimeType, size: p.bytes.length), p.bytes);

  PendingCommand? byId(String id) => _list.where((c) => c.id == id).firstOrNull;

  /// Commands in dependency order, then in the order they were made (§5.3).
  List<PendingCommand> _ordered() {
    final byId = {for (final c in _list) c.id: c};
    final out = <PendingCommand>[];
    final seen = <String>{};
    void visit(PendingCommand c) {
      if (!seen.add(c.id)) return;
      for (final d in c.dependsOn) {
        final dep = byId[d];
        if (dep != null) visit(dep);
      }
      out.add(c);
    }

    for (final c in [..._list]..sort((a, b) => a.createdAt.compareTo(b.createdAt))) {
      visit(c);
    }
    return out;
  }

  /// Send what can be sent now. [force] ignores the backoff (the person pressed "Send now").
  Future<void> sync({bool force = false}) async {
    if (_syncing) return;
    final session = ref.read(sessionProvider).value;
    if (session?.workspaceId == null) return;
    _syncing = true;
    try {
      await future;
      final config = ref.read(configProvider);
      final executor = CommandExecutor(ref.read(apiServiceProvider), _store);
      for (final c in _ordered()) {
        if (!c.open) continue;
        // A command belongs to the workspace it was made in; it waits until the person is there again.
        if (c.workspaceId != session!.workspaceId) continue;
        final now = DateTime.now();
        if (now.difference(c.createdAt) > config.offlineRetention) {
          c
            ..status = CommandStatus.expired
            ..lastCode = 'expired'
            ..lastError = 'Not sent within the ${config.offlineRetentionDays}-day offline retention. '
                'Nothing was applied; do it again if it still holds.';
          await _store.save(c);
          _publish();
          continue;
        }
        final deps = [for (final d in c.dependsOn) byId(d)].whereType<PendingCommand>();
        if (deps.any((d) => d.open)) continue;
        final failed = deps.where((d) => d.needsPerson).toList();
        if (failed.isNotEmpty) {
          c
            ..status = CommandStatus.rejected
            ..lastCode = 'dependency'
            ..lastError = 'It depends on “${failed.first.label}”, which was not accepted.';
          await _store.save(c);
          _publish();
          continue;
        }
        if (!force && c.nextAttemptAt != null && c.nextAttemptAt!.isAfter(now)) continue;
        c.status = CommandStatus.sending;
        _publish();
        try {
          c.note = await executor.run(c);
          c
            ..status = CommandStatus.accepted
            ..lastError = null
            ..lastCode = null;
          await _store.remove(c); // accepted: the draft and its attachments leave the device (§5.3 step 8)
          _publish();
        } on Problem catch (p) {
          c.attempts++;
          c.lastError = p.message;
          c.lastCode = p.code.name;
          switch (outcomeOf(p)) {
            case Outcome.stopSync:
              c.status = CommandStatus.queued;
              c.attempts--; // not the command's fault
              await _store.save(c);
              _publish();
              return;
            case Outcome.retryLater:
              if (c.attempts >= maxAttempts) {
                c
                  ..status = CommandStatus.rejected
                  ..lastError = 'Tried $maxAttempts times without an answer. ${p.message}';
              } else {
                c
                  ..status = CommandStatus.queued
                  ..nextAttemptAt = DateTime.now().add(backoff(c.attempts));
              }
            case Outcome.conflict:
              c
                ..status = CommandStatus.conflict
                ..reviewItem = p.reviewItem;
            case Outcome.expired:
              c.status = CommandStatus.expired;
            case Outcome.rejected:
              c.status = CommandStatus.rejected;
          }
          await _store.save(c);
          _publish();
        }
      }
    } finally {
      _syncing = false;
    }
  }

  /// Send it again, now (after the person fixed what was wrong, or to retry before the backoff).
  Future<void> retry(String id) async {
    final c = byId(id);
    if (c == null) return;
    c
      ..status = CommandStatus.queued
      ..attempts = 0
      ..nextAttemptAt = null;
    await _store.save(c);
    _publish();
    await sync(force: true);
  }

  /// The person gives up a rejected, conflicting or expired command: it leaves the device.
  Future<void> discard(String id) async {
    final c = byId(id);
    if (c == null) return;
    await _store.remove(c);
    state = AsyncData(_list.where((x) => x.id != id).toList());
  }

  /// Unsent work, as the person would describe it: what a wipe would lose.
  List<PendingCommand> get unsent => _list.where((c) => c.open || c.needsPerson).toList();
}

final queueProvider = AsyncNotifierProvider<QueueController, List<PendingCommand>>(QueueController.new);

/// Unsent commands whose target is this record: shown on it as pending ("not yet in ARGUS").
final pendingForProvider = Provider.family<List<PendingCommand>, String>((ref, uid) {
  final all = ref.watch(queueProvider).value ?? const <PendingCommand>[];
  return all.where((c) => c.status != CommandStatus.accepted && (c.target == uid || c.payload['asset_uid'] == uid ||
      c.payload['ticket_uid'] == uid || c.payload['position_uid'] == uid)).toList();
});

/// What happened to a command sent at once: what a screen tells the person.
extension SendNow on QueueController {
  Future<PendingCommand> sendNow(PendingCommand c) async {
    await sync(force: true);
    return byId(c.id) ?? c;
  }
}

String describe(PendingCommand c) => switch (c.status) {
      CommandStatus.accepted => c.note ?? 'Sent.',
      CommandStatus.queued || CommandStatus.sending =>
        'Saved on this device. It is sent when ARGUS can be reached; see Unsent changes.',
      CommandStatus.conflict => 'It changed meanwhile: sent to review instead (${c.lastError ?? ''}).',
      CommandStatus.expired => c.lastError ?? 'Too old to send.',
      CommandStatus.rejected => 'Not accepted: ${c.lastError ?? ''}',
    };
