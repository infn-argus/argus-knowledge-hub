import 'package:argus_api/api.dart' as api;

import 'api_service.dart';

/// Whether the assistant can answer here, and if not, why (asked before it is offered).
class AskAvailability {
  const AskAvailability({required this.usable, this.reason});

  final bool usable;
  final String? reason;
}

/// What the server says while it works out an answer (backend services/ask.py, `ask_events`).
sealed class AskEvent {
  const AskEvent();
}

/// The conversation the turn belongs to: given on the first event, used to continue it.
class AskConversationStarted extends AskEvent {
  const AskConversationStarted(this.id);
  final String id;
}

/// More of the answer, as it is written.
class AskText extends AskEvent {
  const AskText(this.text);
  final String text;
}

/// What was written so far preceded lookups: it was not the answer, so it is cleared.
class AskTextReset extends AskEvent {
  const AskTextReset();
}

/// A lookup in the records: started ([done] false), then finished with a short summary.
class AskLookup extends AskEvent {
  const AskLookup({required this.index, required this.tool, this.summary, this.error, this.done = false});
  final int index;
  final String tool;
  final String? summary;
  final String? error;
  final bool done;
}

/// The end of the turn: the whole answer, and whether it was cut short.
class AskDone extends AskEvent {
  const AskDone({required this.answer, required this.stopped, this.error});
  final String answer;
  final String stopped; // answered | exhausted | failed | cancelled
  final String? error;
}

class AskTurn {
  AskTurn({required this.question, this.answer = '', List<AskLookup>? lookups, this.stopped, this.error})
      : lookups = lookups ?? [];

  final String question;
  String answer;
  final List<AskLookup> lookups;
  String? stopped;
  String? error;

  bool get finished => stopped != null;
}

class AskConversationSummary {
  const AskConversationSummary({required this.id, required this.title, this.updatedAt});
  final String id;
  final String title;
  final DateTime? updatedAt;
}

/// Questions answered from the workspace's records (the web's Ask page). Read-only: the lookups
/// behind it see what the person may see, no more. Nothing of it is kept on the device.
class AskRepository {
  AskRepository(this._api);

  final ApiService _api;

  Future<AskAvailability> availability() async {
    final s = await _api.call((c) => _api.ai(c).status());
    final usable = s.configured && s.enabled && s.validated;
    return AskAvailability(
        usable: usable,
        reason: usable ? null : (s.reason ?? 'The assistant is not set up for this workspace (Administration → AI).'));
  }

  Stream<AskEvent> ask(String question, {String? conversationId}) async* {
    await for (final e in _api.events('/v1/ai/chat', {
      'question': question,
      'conversation_id': ?conversationId,
    })) {
      switch (e['type']) {
        case 'conversation':
          yield AskConversationStarted(e['id'].toString());
        case 'text':
          yield AskText((e['text'] ?? '').toString());
        case 'text_reset':
          yield const AskTextReset();
        case 'step_start':
          yield AskLookup(index: (e['index'] as num?)?.toInt() ?? 0, tool: (e['tool'] ?? '').toString());
        case 'step':
          yield AskLookup(
            index: (e['index'] as num?)?.toInt() ?? 0,
            tool: (e['tool'] ?? '').toString(),
            summary: e['summary']?.toString(),
            error: e['error']?.toString(),
            done: true,
          );
        case 'done':
          yield AskDone(
            answer: (e['answer'] ?? '').toString(),
            stopped: (e['stopped'] ?? 'answered').toString(),
            error: e['error']?.toString(),
          );
      }
    }
  }

  Future<List<AskConversationSummary>> conversations() async {
    final list = await _api.call((c) => _api.ai(c).listConversations());
    return [
      for (final c in list) AskConversationSummary(id: c.id, title: c.title, updatedAt: c.updatedAt),
    ];
  }

  /// A conversation's turns: each question with the answer that followed it.
  Future<List<AskTurn>> conversation(String id) async {
    final d = await _api.call((c) => _api.ai(c).getConversation(id));
    final turns = <AskTurn>[];
    for (final m in d.messages) {
      if (m.role == 'user') {
        turns.add(AskTurn(question: m.content));
      } else if (turns.isNotEmpty) {
        turns.last
          ..answer = m.content
          ..stopped = m.stopped ?? 'answered'
          ..error = m.error
          ..lookups.addAll([
            for (final (i, s) in (m.steps ?? const <api.AskStep>[]).indexed)
              AskLookup(index: i, tool: s.tool, error: s.error, done: true),
          ]);
      }
    }
    return turns;
  }
}
