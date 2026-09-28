/// What a scanned label or an opened link asks for (revision §24.5, I-MOB-6).
///
/// Only an https link on the configured ARGUS host is followed as a path. Anything that looks like
/// another URL or scheme is refused (a label must never open a browser, a phone number or a
/// script). Plain text is a label value: a key, an inventory number, an old Jira or Insight
/// identifier, and goes to lookup.
sealed class ScanResult {
  const ScanResult();
}

class ArgusPath extends ScanResult {
  const ArgusPath(this.path);
  final String path; // e.g. /asset/<uid>
}

class LabelValue extends ScanResult {
  const LabelValue(this.value);
  final String value;
}

class Refused extends ScanResult {
  const Refused(this.reason);
  final String reason;
}

const _neverFollowed = {
  'javascript', 'data', 'file', 'tel', 'sms', 'smsto', 'mailto', 'intent', 'geo', 'market', 'wifi', 'vbscript', 'blob', 'content',
  'http', 'https', 'ftp', 'ws', 'wss',
};

const _argusKinds = {'asset', 'position', 'installation', 'document', 'ticket', 'review', 'lookup'};

ScanResult parseScan(String raw, {required String linkHost}) {
  final text = raw.trim();
  if (text.isEmpty) return const Refused('The label is empty.');
  if (text.length > 512) return const Refused('The label is too long to be an ARGUS label.');
  if (RegExp(r'[\x00-\x1f]').hasMatch(text)) return const Refused('The label contains control characters.');

  // Something that is a link or a scheme a label must never trigger. A bare "ABC:12" is still a
  // label value (some old inventory numbers have a colon).
  final scheme = RegExp(r'^([a-zA-Z][a-zA-Z0-9+.-]*):').firstMatch(text)?.group(1)?.toLowerCase();
  if (scheme != null && (text.contains('://') || _neverFollowed.contains(scheme))) {
    // Something with a scheme. Only https on our host is followed.
    final uri = Uri.tryParse(text);
    if (scheme != 'https' || uri == null) return Refused('Links of type "$scheme:" are not followed.');
    if (uri.host.toLowerCase() != linkHost.toLowerCase()) {
      return Refused('The link points to ${uri.host}, not to ARGUS. It was not opened.');
    }
    final segments = uri.pathSegments.where((s) => s.isNotEmpty).toList();
    if (segments.length < 2 || !_argusKinds.contains(segments.first)) {
      return const Refused('The link is on the ARGUS host but is not a record link.');
    }
    return ArgusPath('/${segments.map(Uri.encodeComponent).join('/')}');
  }
  if (text.startsWith('/')) {
    final segments = text.split('/').where((s) => s.isNotEmpty).toList();
    if (segments.length >= 2 && _argusKinds.contains(segments.first)) {
      return ArgusPath('/${segments.map(Uri.encodeComponent).join('/')}');
    }
  }
  return LabelValue(text);
}
