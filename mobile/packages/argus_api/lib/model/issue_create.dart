//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class IssueCreate {
  /// Returns a new [IssueCreate] instance.
  IssueCreate({
    this.assetUid,
    this.assignee,
    this.attributes,
    this.createdBy,
    this.description,
    this.dueDate,
    this.labels = const [],
    this.priority,
    this.schemaUid,
    this.state = 'new',
    required this.title,
    required this.uid,
  });

  String? assetUid;

  String? assignee;

  ///
  /// Please note: This property should have been non-nullable! Since the specification file
  /// does not include a default value (using the "default:" property), however, the generated
  /// source code must fall back to having a nullable type.
  /// Consider adding a "default:" property in the specification file to hide this note.
  ///
  Object? attributes;

  String? createdBy;

  String? description;

  DateTime? dueDate;

  List<String> labels;

  String? priority;

  String? schemaUid;

  String state;

  String title;

  String uid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is IssueCreate &&
    other.assetUid == assetUid &&
    other.assignee == assignee &&
    other.attributes == attributes &&
    other.createdBy == createdBy &&
    other.description == description &&
    other.dueDate == dueDate &&
    _deepEquality.equals(other.labels, labels) &&
    other.priority == priority &&
    other.schemaUid == schemaUid &&
    other.state == state &&
    other.title == title &&
    other.uid == uid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assetUid == null ? 0 : assetUid!.hashCode) +
    (assignee == null ? 0 : assignee!.hashCode) +
    (attributes == null ? 0 : attributes!.hashCode) +
    (createdBy == null ? 0 : createdBy!.hashCode) +
    (description == null ? 0 : description!.hashCode) +
    (dueDate == null ? 0 : dueDate!.hashCode) +
    (labels.hashCode) +
    (priority == null ? 0 : priority!.hashCode) +
    (schemaUid == null ? 0 : schemaUid!.hashCode) +
    (state.hashCode) +
    (title.hashCode) +
    (uid.hashCode);

  @override
  String toString() => 'IssueCreate[assetUid=$assetUid, assignee=$assignee, attributes=$attributes, createdBy=$createdBy, description=$description, dueDate=$dueDate, labels=$labels, priority=$priority, schemaUid=$schemaUid, state=$state, title=$title, uid=$uid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.assetUid != null) {
      json[r'asset_uid'] = this.assetUid;
    } else {
      json[r'asset_uid'] = null;
    }
    if (this.assignee != null) {
      json[r'assignee'] = this.assignee;
    } else {
      json[r'assignee'] = null;
    }
    if (this.attributes != null) {
      json[r'attributes'] = this.attributes;
    } else {
      json[r'attributes'] = null;
    }
    if (this.createdBy != null) {
      json[r'created_by'] = this.createdBy;
    } else {
      json[r'created_by'] = null;
    }
    if (this.description != null) {
      json[r'description'] = this.description;
    } else {
      json[r'description'] = null;
    }
    if (this.dueDate != null) {
      json[r'due_date'] = this.dueDate!.toUtc().toIso8601String();
    } else {
      json[r'due_date'] = null;
    }
      json[r'labels'] = this.labels;
    if (this.priority != null) {
      json[r'priority'] = this.priority;
    } else {
      json[r'priority'] = null;
    }
    if (this.schemaUid != null) {
      json[r'schema_uid'] = this.schemaUid;
    } else {
      json[r'schema_uid'] = null;
    }
      json[r'state'] = this.state;
      json[r'title'] = this.title;
      json[r'uid'] = this.uid;
    return json;
  }

  /// Returns a new [IssueCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static IssueCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "IssueCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "IssueCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return IssueCreate(
        assetUid: mapValueOfType<String>(json, r'asset_uid'),
        assignee: mapValueOfType<String>(json, r'assignee'),
        attributes: mapValueOfType<Object>(json, r'attributes'),
        createdBy: mapValueOfType<String>(json, r'created_by'),
        description: mapValueOfType<String>(json, r'description'),
        dueDate: mapDateTime(json, r'due_date', r''),
        labels: json[r'labels'] is Iterable
            ? (json[r'labels'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        priority: mapValueOfType<String>(json, r'priority'),
        schemaUid: mapValueOfType<String>(json, r'schema_uid'),
        state: mapValueOfType<String>(json, r'state') ?? 'new',
        title: mapValueOfType<String>(json, r'title')!,
        uid: mapValueOfType<String>(json, r'uid')!,
      );
    }
    return null;
  }

  static List<IssueCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <IssueCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = IssueCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, IssueCreate> mapFromJson(dynamic json) {
    final map = <String, IssueCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = IssueCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of IssueCreate-objects as value to a dart map
  static Map<String, List<IssueCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<IssueCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = IssueCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'title',
    'uid',
  };
}

