//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentOut {
  /// Returns a new [DocumentOut] instance.
  DocumentOut({
    required this.authorityLevel,
    required this.code,
    required this.confidentiality,
    required this.createdAt,
    this.currentRevisionUid,
    this.documentTypeUid,
    this.isGlobal = false,
    this.ownerUserId,
    this.responsibleServiceAssetUid,
    this.retentionClass = '5y',
    this.retiredAt,
    required this.source_,
    this.supersededByUid,
    required this.title,
    required this.uid,
    required this.updatedAt,
    required this.workspaceId,
  });

  String authorityLevel;

  String code;

  String confidentiality;

  DateTime createdAt;

  String? currentRevisionUid;

  String? documentTypeUid;

  bool isGlobal;

  String? ownerUserId;

  String? responsibleServiceAssetUid;

  String retentionClass;

  DateTime? retiredAt;

  String source_;

  String? supersededByUid;

  String title;

  String uid;

  DateTime updatedAt;

  String workspaceId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentOut &&
    other.authorityLevel == authorityLevel &&
    other.code == code &&
    other.confidentiality == confidentiality &&
    other.createdAt == createdAt &&
    other.currentRevisionUid == currentRevisionUid &&
    other.documentTypeUid == documentTypeUid &&
    other.isGlobal == isGlobal &&
    other.ownerUserId == ownerUserId &&
    other.responsibleServiceAssetUid == responsibleServiceAssetUid &&
    other.retentionClass == retentionClass &&
    other.retiredAt == retiredAt &&
    other.source_ == source_ &&
    other.supersededByUid == supersededByUid &&
    other.title == title &&
    other.uid == uid &&
    other.updatedAt == updatedAt &&
    other.workspaceId == workspaceId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (authorityLevel.hashCode) +
    (code.hashCode) +
    (confidentiality.hashCode) +
    (createdAt.hashCode) +
    (currentRevisionUid == null ? 0 : currentRevisionUid!.hashCode) +
    (documentTypeUid == null ? 0 : documentTypeUid!.hashCode) +
    (isGlobal.hashCode) +
    (ownerUserId == null ? 0 : ownerUserId!.hashCode) +
    (responsibleServiceAssetUid == null ? 0 : responsibleServiceAssetUid!.hashCode) +
    (retentionClass.hashCode) +
    (retiredAt == null ? 0 : retiredAt!.hashCode) +
    (source_.hashCode) +
    (supersededByUid == null ? 0 : supersededByUid!.hashCode) +
    (title.hashCode) +
    (uid.hashCode) +
    (updatedAt.hashCode) +
    (workspaceId.hashCode);

  @override
  String toString() => 'DocumentOut[authorityLevel=$authorityLevel, code=$code, confidentiality=$confidentiality, createdAt=$createdAt, currentRevisionUid=$currentRevisionUid, documentTypeUid=$documentTypeUid, isGlobal=$isGlobal, ownerUserId=$ownerUserId, responsibleServiceAssetUid=$responsibleServiceAssetUid, retentionClass=$retentionClass, retiredAt=$retiredAt, source_=$source_, supersededByUid=$supersededByUid, title=$title, uid=$uid, updatedAt=$updatedAt, workspaceId=$workspaceId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'authority_level'] = this.authorityLevel;
      json[r'code'] = this.code;
      json[r'confidentiality'] = this.confidentiality;
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
    if (this.currentRevisionUid != null) {
      json[r'current_revision_uid'] = this.currentRevisionUid;
    } else {
      json[r'current_revision_uid'] = null;
    }
    if (this.documentTypeUid != null) {
      json[r'document_type_uid'] = this.documentTypeUid;
    } else {
      json[r'document_type_uid'] = null;
    }
      json[r'is_global'] = this.isGlobal;
    if (this.ownerUserId != null) {
      json[r'owner_user_id'] = this.ownerUserId;
    } else {
      json[r'owner_user_id'] = null;
    }
    if (this.responsibleServiceAssetUid != null) {
      json[r'responsible_service_asset_uid'] = this.responsibleServiceAssetUid;
    } else {
      json[r'responsible_service_asset_uid'] = null;
    }
      json[r'retention_class'] = this.retentionClass;
    if (this.retiredAt != null) {
      json[r'retired_at'] = this.retiredAt!.toUtc().toIso8601String();
    } else {
      json[r'retired_at'] = null;
    }
      json[r'source'] = this.source_;
    if (this.supersededByUid != null) {
      json[r'superseded_by_uid'] = this.supersededByUid;
    } else {
      json[r'superseded_by_uid'] = null;
    }
      json[r'title'] = this.title;
      json[r'uid'] = this.uid;
      json[r'updated_at'] = this.updatedAt.toUtc().toIso8601String();
      json[r'workspace_id'] = this.workspaceId;
    return json;
  }

  /// Returns a new [DocumentOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentOut(
        authorityLevel: mapValueOfType<String>(json, r'authority_level')!,
        code: mapValueOfType<String>(json, r'code')!,
        confidentiality: mapValueOfType<String>(json, r'confidentiality')!,
        createdAt: mapDateTime(json, r'created_at', r'')!,
        currentRevisionUid: mapValueOfType<String>(json, r'current_revision_uid'),
        documentTypeUid: mapValueOfType<String>(json, r'document_type_uid'),
        isGlobal: mapValueOfType<bool>(json, r'is_global') ?? false,
        ownerUserId: mapValueOfType<String>(json, r'owner_user_id'),
        responsibleServiceAssetUid: mapValueOfType<String>(json, r'responsible_service_asset_uid'),
        retentionClass: mapValueOfType<String>(json, r'retention_class') ?? '5y',
        retiredAt: mapDateTime(json, r'retired_at', r''),
        source_: mapValueOfType<String>(json, r'source')!,
        supersededByUid: mapValueOfType<String>(json, r'superseded_by_uid'),
        title: mapValueOfType<String>(json, r'title')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        updatedAt: mapDateTime(json, r'updated_at', r'')!,
        workspaceId: mapValueOfType<String>(json, r'workspace_id')!,
      );
    }
    return null;
  }

  static List<DocumentOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentOut> mapFromJson(dynamic json) {
    final map = <String, DocumentOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentOut-objects as value to a dart map
  static Map<String, List<DocumentOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'authority_level',
    'code',
    'confidentiality',
    'created_at',
    'source',
    'title',
    'uid',
    'updated_at',
    'workspace_id',
  };
}

