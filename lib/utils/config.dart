class Config {
  static const bool useMockData = true;

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8080/api',
  );

  static const String apiKey = String.fromEnvironment(
    'API_KEY',
    defaultValue: '',
  );

  static const String vertexAiProjectId = String.fromEnvironment(
    'VERTEX_AI_PROJECT_ID',
    defaultValue: '',
  );

  static const String vertexAiLocation = String.fromEnvironment(
    'VERTEX_AI_LOCATION',
    defaultValue: 'asia-northeast1',
  );

  static const int maxFileSize = 50 * 1024 * 1024;

  static const List<String> allowedFileExtensions = ['pdf'];
}