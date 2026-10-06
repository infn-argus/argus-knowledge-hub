//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AssetCommentOut {
  /// Returns a new [AssetCommentOut] instance.
  AssetCommentOut({
    required this.assetUid,
    required this.author,
    this.backendId,
    this.backendUrl,
    required this.created,
    required this.text,
    required this.uid,
    required this.updated,
  });

  String assetUid;

  String author;

  String? backendId;

  String? backendUrl;

  DateTime created;

  String text;

  String uid;

  DateTime updated;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AssetCommentOut &&
    other.assetUid == assetUid &&
    other.author == author &&
    other.backendId == backendId &&
    other.backendUrl == backendUrl &&
    other.created == created &&
    other.text == text &&
    other.uid == uid &&
    other.updated == updated;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assetUid.hashCode) +
    (author.hashCode) +
    (backendId == null ? 0 : backendId!.hashCode) +
    (backendUrl == null ? 0 : backendUrl!.hashCode) +
    (created.hashCode) +
    (text.hashCode) +
    (uid.hashCode) +
    (updated.hashCode);

  @override
  String toString() => 'AssetCommentOut[assetUid=$assetUid, author=$author, backendId=$backendId, backendUrl=$backendUrl, created=$created, text=$text, uid=$uid, updated=$updated]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'asset_uid'] = this.assetUid;
      json[r'author'] = this.author;
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
      json[r'created'] = this.created.toUtc().toIso8601String();
      json[r'text'] = this.text;
      json[r'uid'] = this.uid;
      json[r'updated'] = this.updated.toUtc().toIso8601String();
    return json;
  }

  /// Returns a new [AssetCommentOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AssetCommentOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AssetCommentOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AssetCommentOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AssetCommentOut(
        assetUid: mapValueOfType<String>(json, r'asset_uid')!,
        author: mapValueOfType<String>(json, r'author')!,
        backendId: mapValueOfType<String>(json, r'backend_id'),
        backendUrl: mapValueOfType<String>(json, r'backend_url'),
        created: mapDateTime(json, r'created', r'')!,
        text: mapValueOfType<String>(json, r'text')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        updated: mapDateTime(json, r'updated', r'')!,
      );
    }
    return null;
  }

  static List<AssetCommentOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AssetCommentOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AssetCommentOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AssetCommentOut> mapFromJson(dynamic json) {
    final map = <String, AssetCommentOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AssetCommentOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AssetCommentOut-objects as value to a dart map
  static Map<String, List<AssetCommentOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AssetCommentOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AssetCommentOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'asset_uid',
    'author',
    'created',
    'text',
    'uid',
    'updated',
  };
}

