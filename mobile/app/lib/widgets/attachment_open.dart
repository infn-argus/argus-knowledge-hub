import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../app/providers.dart';
import '../domain/capture.dart';
import '../features/capture/media_source.dart';
import 'attach_menu.dart';
import 'auth_image.dart';

/// Opens an attachment as what it is: a photo here, a place in the maps app, a video, a recorded note or a
/// document in the app the phone plays or shows it with.
Future<void> openAttachment(BuildContext context, WidgetRef ref, AttachmentInfo f) async {
  final mime = f.mimeType ?? '';
  if (mime.startsWith('image/')) {
    await showDialog<void>(
      context: context,
      builder: (_) => Dialog(child: InteractiveViewer(child: AuthImage(f.uid, fit: BoxFit.contain))),
    );
    return;
  }
  final messenger = ScaffoldMessenger.of(context);
  try {
    final bytes = await ref.read(apiServiceProvider).getBytes('/v1/attachments/${f.uid}');
    if (mime == 'application/geo+json') {
      final p = readPlace(bytes);
      if (p == null) throw const FormatException('not a place');
      await launchUrl(Uri.https('www.google.com', '/maps/search/', {'api': '1', 'query': '${p.lat},${p.lon}'}),
          mode: LaunchMode.externalApplication);
      return;
    }
    if (kIsWeb) throw UnsupportedError('web');
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/${f.uid}-${f.filename.replaceAll(RegExp(r'[/\\]'), '_')}');
    await file.writeAsBytes(bytes, flush: true);
    final r = await OpenFilex.open(file.path, type: mime.isEmpty ? null : mime);
    if (r.type != ResultType.done) {
      messenger.showSnackBar(SnackBar(content: Text('No app on this phone opens ${kindOf(mime).toLowerCase()}s.')));
    }
  } catch (_) {
    messenger.showSnackBar(SnackBar(content: Text('${f.filename} could not be opened.')));
  }
}

/// One attachment in a record's list.
class AttachmentTile extends ConsumerWidget {
  const AttachmentTile(this.f, {super.key});

  final AttachmentInfo f;

  @override
  Widget build(BuildContext context, WidgetRef ref) => ListTile(
        key: Key('attachment-${f.uid}'),
        dense: true,
        leading: Icon(iconOf(f.mimeType)),
        title: Text(f.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text([kindOf(f.mimeType ?? ''), if (f.size != null) _size(f.size!)].join(' · ')),
        onTap: () => openAttachment(context, ref, f),
      );

  static String _size(int b) => b >= 1024 * 1024 ? '${(b / 1024 / 1024).toStringAsFixed(1)} MB' : '${(b / 1024).ceil()} KB';
}
