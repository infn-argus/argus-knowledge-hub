//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AssetHistoryOut {
  /// Returns a new [AssetHistoryOut] instance.
  AssetHistoryOut({
    required this.assetUid,
    required this.author,
    this.backendId,
    required this.details,
    required this.timestamp,
    required this.type,
    required this.uid,
  });

  String assetUid;

  String author;

  String? backendId;

  String details;

  DateTime timestamp;

  String type;

  String uid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AssetHistoryOut &&
    other.assetUid == assetUid &&
    other.author == author &&
    other.backendId == backendId &&
    other.details == details &&
    other.timestamp == timestamp &&
    other.type == type &&
    other.uid == uid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assetUid.hashCode) +
    (author.hashCode) +
    (backendId == null ? 0 : backendId!.hashCode) +
    (details.hashCode) +
    (timestamp.hashCode) +
    (type.hashCode) +
    (uid.hashCode);

  @override
  String toString() => 'AssetHistoryOut[assetUid=$assetUid, author=$author, backendId=$backendId, details=$details, timestamp=$timestamp, type=$type, uid=$uid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'asset_uid'] = this.assetUid;
      json[r'author'] = this.author;
    if (this.backendId != null) {
      json[r'backend_id'] = this.backendId;
    } else {
      json[r'backend_id'] = null;
    }
      json[r'details'] = this.details;
      json[r'timestamp'] = this.timestamp.toUtc().toIso8601String();
      json[r'type'] = this.type;
      json[r'uid'] = this.uid;
    return json;
  }

  /// Returns a new [AssetHistoryOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AssetHistoryOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AssetHistoryOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AssetHistoryOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AssetHistoryOut(
        assetUid: mapValueOfType<String>(json, r'asset_uid')!,
        author: mapValueOfType<String>(json, r'author')!,
        backendId: mapValueOfType<String>(json, r'backend_id'),
        details: mapValueOfType<String>(json, r'details')!,
        timestamp: mapDateTime(json, r'timestamp', r'')!,
        type: mapValueOfType<String>(json, r'type')!,
        uid: mapValueOfType<String>(json, r'uid')!,
      );
    }
    return null;
  }

  static List<AssetHistoryOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AssetHistoryOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AssetHistoryOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AssetHistoryOut> mapFromJson(dynamic json) {
    final map = <String, AssetHistoryOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AssetHistoryOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AssetHistoryOut-objects as value to a dart map
  static Map<String, List<AssetHistoryOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AssetHistoryOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AssetHistoryOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'asset_uid',
    'author',
    'details',
    'timestamp',
    'type',
    'uid',
  };
}

