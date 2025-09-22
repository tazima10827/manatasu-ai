import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import '../models/problem_generation_params.dart';
import '../models/generated_problem.dart';
import '../services/api_service.dart';
import '../utils/config.dart';

class ProblemGeneratorProvider extends ChangeNotifier {
  bool _isLoading = false;
  PlatformFile? _uploadedPDF;
  ProblemGenerationParams? _params;
  List<GeneratedProblem> _generatedProblems = [];
  String? _errorMessage;
  Uint8List? _generatedPdfBytes;

  bool get isLoading => _isLoading;
  PlatformFile? get uploadedPDF => _uploadedPDF;
  ProblemGenerationParams? get params => _params;
  List<GeneratedProblem> get generatedProblems => _generatedProblems;
  String? get errorMessage => _errorMessage;
  Uint8List? get generatedPdfBytes => _generatedPdfBytes;

  final ApiService _apiService = ApiService();

  Future<void> uploadPDF() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        allowMultiple: false,
      );

      if (result != null) {
        _uploadedPDF = result.files.first;
        _errorMessage = null;
        notifyListeners();
      }
    } catch (e) {
      _errorMessage = 'PDFのアップロードに失敗しました: $e';
      notifyListeners();
    }
  }

  void clearUploadedPDF() {
    _uploadedPDF = null;
    notifyListeners();
  }

  void setParams(ProblemGenerationParams params) {
    _params = params;
    notifyListeners();
  }

  Future<void> generateProblems() async {
    if (_uploadedPDF == null || _params == null) {
      _errorMessage = 'PDFとパラメータを設定してください';
      notifyListeners();
      return;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (Config.useMockData) {
        await Future.delayed(const Duration(seconds: 2));
        _generatedProblems = ApiService.getMockProblems(_params!);
      } else {
        _generatedProblems = await _apiService.generateProblems(
          pdfBytes: _uploadedPDF!.bytes!,
          params: _params!,
        );
      }

      await _generatePDF();

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = '問題生成に失敗しました: $e';
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> addMoreProblems({
    PlatformFile? additionalPDF,
    required ProblemGenerationParams params,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      List<GeneratedProblem> newProblems;

      if (Config.useMockData) {
        await Future.delayed(const Duration(seconds: 2));
        newProblems = ApiService.getMockProblems(params);
        // 既存の問題と重複しないようにIDを調整
        final startIndex = _generatedProblems.length;
        for (int i = 0; i < newProblems.length; i++) {
          newProblems[i] = GeneratedProblem(
            id: 'problem_${startIndex + i + 1}',
            question: newProblems[i].question.replaceAll('問題 ${i + 1}', '問題 ${startIndex + i + 1}'),
            answer: newProblems[i].answer,
            explanation: newProblems[i].explanation,
            choices: newProblems[i].choices,
            difficulty: newProblems[i].difficulty,
            subject: newProblems[i].subject,
            grade: newProblems[i].grade,
            sourceFile: additionalPDF?.name ?? _uploadedPDF?.name ?? 'sample.pdf',
            sourcePage: newProblems[i].sourcePage,
            sourceUri: newProblems[i].sourceUri,
            generatedAt: newProblems[i].generatedAt,
          );
        }
      } else {
        final pdfBytes = additionalPDF?.bytes ?? _uploadedPDF!.bytes!;
        newProblems = await _apiService.generateProblems(
          pdfBytes: pdfBytes,
          params: params,
        );
      }

      _generatedProblems.addAll(newProblems);
      await _generatePDF();

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = '追加問題の生成に失敗しました: $e';
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _generatePDF() async {
    final pdf = pw.Document();

    for (var i = 0; i < _generatedProblems.length; i++) {
      final problem = _generatedProblems[i];

      pdf.addPage(
        pw.Page(
          pageFormat: PdfPageFormat.a4,
          build: (pw.Context context) {
            return pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  '問題 ${i + 1}',
                  style: pw.TextStyle(
                    fontSize: 18,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.SizedBox(height: 10),
                pw.Text(
                  problem.question,
                  style: const pw.TextStyle(fontSize: 14),
                ),
                pw.SizedBox(height: 20),
                if (problem.choices != null && problem.choices!.isNotEmpty) ...[
                  pw.Text('選択肢:', style: pw.TextStyle(fontWeight: pw.FontWeight.bold)),
                  pw.SizedBox(height: 5),
                  ...problem.choices!.asMap().entries.map((entry) {
                    return pw.Padding(
                      padding: const pw.EdgeInsets.only(left: 20, top: 5),
                      child: pw.Text('${entry.key + 1}. ${entry.value}'),
                    );
                  }).toList(),
                  pw.SizedBox(height: 20),
                ],
                pw.Text(
                  '解答: ${problem.answer}',
                  style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                ),
                pw.SizedBox(height: 10),
                pw.Text(
                  '解説: ${problem.explanation}',
                  style: const pw.TextStyle(fontSize: 12),
                ),
                pw.SizedBox(height: 20),
                pw.Container(
                  padding: const pw.EdgeInsets.all(10),
                  decoration: pw.BoxDecoration(
                    border: pw.Border.all(width: 1),
                    borderRadius: const pw.BorderRadius.all(pw.Radius.circular(5)),
                  ),
                  child: pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.start,
                    children: [
                      pw.Text('出典情報', style: pw.TextStyle(fontWeight: pw.FontWeight.bold)),
                      pw.SizedBox(height: 5),
                      pw.Text('ファイル: ${problem.sourceFile}'),
                      pw.Text('ページ: ${problem.sourcePage}'),
                      if (problem.sourceUri != null)
                        pw.Text('URI: ${problem.sourceUri}'),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      );
    }

    _generatedPdfBytes = await pdf.save();
  }

  void removeProblem(int index) {
    if (index >= 0 && index < _generatedProblems.length) {
      _generatedProblems.removeAt(index);
      notifyListeners();
    }
  }

  void reorderProblems(int oldIndex, int newIndex) {
    if (oldIndex < newIndex) {
      newIndex -= 1;
    }
    final item = _generatedProblems.removeAt(oldIndex);
    _generatedProblems.insert(newIndex, item);
    notifyListeners();
  }

  void reset() {
    _isLoading = false;
    _uploadedPDF = null;
    _params = null;
    _generatedProblems = [];
    _errorMessage = null;
    _generatedPdfBytes = null;
    notifyListeners();
  }

  void clearForNewGeneration() {
    _isLoading = false;
    _uploadedPDF = null;
    _params = null;
    _errorMessage = null;
    _generatedPdfBytes = null;
    notifyListeners();
  }
}