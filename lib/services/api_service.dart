import 'dart:convert';
import 'dart:typed_data';
import 'dart:math' as math;
import 'package:http/http.dart' as http;
import '../models/problem_generation_params.dart';
import '../models/generated_problem.dart';
import '../utils/config.dart';

class ApiService {
  static const String baseUrl = Config.apiBaseUrl;

  Future<List<GeneratedProblem>> generateProblems({
    required Uint8List pdfBytes,
    required ProblemGenerationParams params,
  }) async {
    try {
      print('Flutter: Starting API request to $baseUrl/generate-problems');
      print('Flutter: API Key configured: ${Config.apiKey.isNotEmpty}');
      print('Flutter: PDF size: ${pdfBytes.length} bytes');

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/generate-problems'),
      );

      request.files.add(
        http.MultipartFile.fromBytes(
          'pdf',
          pdfBytes,
          filename: 'document.pdf',
        ),
      );

      request.fields['params'] = jsonEncode(params.toJson());
      print('Flutter: Request params: ${jsonEncode(params.toJson())}');

      final headers = {
        'Authorization': 'Bearer ${Config.apiKey}',
      };

      request.headers.addAll(headers);
      print('Flutter: Request headers: ${request.headers}');

      print('Flutter: Sending request...');
      final response = await request.send();
      print('Flutter: Response status: ${response.statusCode}');
      print('Flutter: Response headers: ${response.headers}');

      final responseBody = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        print('Flutter: API Response received: ${responseBody.substring(0, math.min(500, responseBody.length))}...');

        final jsonResponse = jsonDecode(responseBody) as Map<String, dynamic>;
        print('Flutter: Parsed JSON response: $jsonResponse');

        final problemsJson = jsonResponse['problems'] as List;
        print('Flutter: Problems count: ${problemsJson.length}');

        final problems = problemsJson
            .map((json) => GeneratedProblem.fromJson(json))
            .toList();

        print('Flutter: Generated problems: ${problems.map((p) => p.question).toList()}');

        return problems;
      } else {
        throw Exception('API Error: ${response.statusCode} - $responseBody');
      }
    } catch (e) {
      throw Exception('Failed to generate problems: $e');
    }
  }

  Future<List<GeneratedProblem>> generateProblemsWithoutPdf({
    required ProblemGenerationParams params,
  }) async {
    try {
      print('Flutter: Starting API request to $baseUrl/generate-problems-no-pdf');
      print('Flutter: API Key configured: ${Config.apiKey.isNotEmpty}');

      final request = http.Request(
        'POST',
        Uri.parse('$baseUrl/generate-problems-no-pdf'),
      );

      request.body = jsonEncode(params.toJson());
      print('Flutter: Request params: ${jsonEncode(params.toJson())}');

      final headers = {
        'Authorization': 'Bearer ${Config.apiKey}',
        'Content-Type': 'application/json',
      };

      request.headers.addAll(headers);
      print('Flutter: Request headers: ${request.headers}');

      print('Flutter: Sending request...');
      final response = await request.send();
      print('Flutter: Response status: ${response.statusCode}');
      print('Flutter: Response headers: ${response.headers}');

      final responseBody = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        print('Flutter: API Response received: ${responseBody.substring(0, math.min(500, responseBody.length))}...');

        final jsonResponse = jsonDecode(responseBody) as Map<String, dynamic>;
        print('Flutter: Parsed JSON response: $jsonResponse');

        final problemsJson = jsonResponse['problems'] as List;
        print('Flutter: Problems count: ${problemsJson.length}');

        final problems = problemsJson
            .map((json) => GeneratedProblem.fromJson(json))
            .toList();

        print('Flutter: Generated problems: ${problems.map((p) => p.question).toList()}');

        return problems;
      } else {
        throw Exception('API Error: ${response.statusCode} - $responseBody');
      }
    } catch (e) {
      throw Exception('Failed to generate problems without PDF: $e');
    }
  }

  Future<Map<String, dynamic>> extractTextFromPdf(Uint8List pdfBytes) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/extract-pdf'),
      );

      request.files.add(
        http.MultipartFile.fromBytes(
          'pdf',
          pdfBytes,
          filename: 'document.pdf',
        ),
      );

      final headers = {
        'Authorization': 'Bearer ${Config.apiKey}',
      };

      request.headers.addAll(headers);

      final response = await request.send();
      final responseBody = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        return jsonDecode(responseBody) as Map<String, dynamic>;
      } else {
        throw Exception('API Error: ${response.statusCode} - $responseBody');
      }
    } catch (e) {
      throw Exception('Failed to extract text from PDF: $e');
    }
  }

  static List<GeneratedProblem> getMockProblems(ProblemGenerationParams params) {
    final now = DateTime.now();
    final problems = <GeneratedProblem>[];

    for (int i = 1; i <= params.problemCount; i++) {
      final choices = params.problemType == '選択問題'
          ? ['選択肢A', '選択肢B', '選択肢C', '選択肢D']
          : null;

      problems.add(
        GeneratedProblem(
          id: 'problem_$i',
          question: '${params.subject}の問題 $i: ${params.specificTopic ?? "基本問題"}に関する${params.problemType}です。',
          answer: params.problemType == '選択問題' ? '選択肢A' : '解答例がここに表示されます',
          explanation: 'この問題は${params.grade}の${params.difficulty}レベルの問題です。詳細な解説がここに表示されます。',
          choices: choices,
          difficulty: params.difficulty,
          subject: params.subject,
          grade: params.grade,
          sourceFile: 'sample.pdf',
          sourcePage: 'p.${10 + i}',
          sourceUri: null,
          generatedAt: now,
        ),
      );
    }

    return problems;
  }
}