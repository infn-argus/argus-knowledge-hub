//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AttachmentOut {
  /// Returns a new [AttachmentOut] instance.
  AttachmentOut({
    this.assetUid,
    this.author,
    this.backendId,
    this.backendUrl,
    required this.createdAt,
    this.fileSize,
    required this.filename,
    this.mimeType,
    this.sha256,
    required this.uid,
    required this.workspaceId,
  });

  String? assetUid;

  String? author;

  String? backendId;

  String? backendUrl;

  DateTime createdAt;

  int? fileSize;

  String filename;

  String? mimeType;

  String? sha256;

  String uid;

  String workspaceId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AttachmentOut &&
    other.assetUid == assetUid &&
    other.author == author &&
    other.backendId == backendId &&
    other.backendUrl == backendUrl &&
    other.createdAt == createdAt &&
    other.fileSize == fileSize &&
    other.filename == filename &&
    other.mimeType == mimeType &&
    other.sha256 == sha256 &&
    other.uid == uid &&
    other.workspaceId == workspaceId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assetUid == null ? 0 : assetUid!.hashCode) +
    (author == null ? 0 : author!.hashCode) +
    (backendId == null ? 0 : backendId!.hashCode) +
    (backendUrl == null ? 0 : backendUrl!.hashCode) +
    (createdAt.hashCode) +
    (fileSize == null ? 0 : fileSize!.hashCode) +
    (filename.hashCode) +
    (mimeType == null ? 0 : mimeType!.hashCode) +
    (sha256 == null ? 0 : sha256!.hashCode) +
    (uid.hashCode) +
    (workspaceId.hashCode);

  @override
  String toString() => 'AttachmentOut[assetUid=$assetUid, author=$author, backendId=$backendId, backendUrl=$backendUrl, createdAt=$createdAt, fileSize=$fileSize, filename=$filename, mimeType=$mimeType, sha256=$sha256, uid=$uid, workspaceId=$workspaceId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.assetUid != null) {
      json[r'asset_uid'] = this.assetUid;
    } else {
      json[r'asset_uid'] = null;
    }
    if (this.author != null) {
      json[r'author'] = this.author;
    } else {
      json[r'author'] = null;
    }
    if (this.backendId != null) {
      json[r'backend_id'] = this.backendId;
    } else {
      json[r'backend_id'] = null;
    }
    if (this.backendUrl != null) {
      json[r'backend_url'] = this.backendUrl;
    } else {
      json[r'backend_url'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
    if (this.fileSize != null) {
      json[r'file_size'] = this.fileSize;
    } else {
      json[r'file_size'] = null;
    }
      json[r'filename'] = this.filename;
    if (this.mimeType != null) {
      json[r'mime_type'] = this.mimeType;
    } else {
      json[r'mime_type'] = null;
    }
    if (this.sha256 != null) {
      json[r'sha256'] = this.sha256;
    } else {
      json[r'sha256'] = null;
    }
      json[r'uid'] = this.uid;
      json[r'workspace_id'] = this.workspaceId;
    return json;
  }

  /// Returns a new [AttachmentOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AttachmentOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AttachmentOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AttachmentOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AttachmentOut(
        assetUid: mapValueOfType<String>(json, r'asset_uid'),
        author: mapValueOfType<String>(json, r'author'),
        backendId: mapValueOfType<String>(json, r'backend_id'),
        backendUrl: mapValueOfType<String>(json, r'backend_url'),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        fileSize: mapValueOfType<int>(json, r'file_size'),
        filename: mapValueOfType<String>(json, r'filename')!,
        mimeType: mapValueOfType<String>(json, r'mime_type'),
        sha256: mapValueOfType<String>(json, r'sha256'),
        uid: mapValueOfType<String>(json, r'uid')!,
        workspaceId: mapValueOfType<String>(json, r'workspace_id')!,
      );
    }
    return null;
  }

  static List<AttachmentOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AttachmentOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AttachmentOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AttachmentOut> mapFromJson(dynamic json) {
    final map = <String, AttachmentOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AttachmentOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AttachmentOut-objects as value to a dart map
  static Map<String, List<AttachmentOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AttachmentOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AttachmentOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'created_at',
    'filename',
    'uid',
    'workspace_id',
  };
}

