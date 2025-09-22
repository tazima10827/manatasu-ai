import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../providers/problem_generator_provider.dart';
import '../models/problem_generation_params.dart';
import 'generation_form_widget.dart';

class AddMoreProblemsDialog extends StatefulWidget {
  const AddMoreProblemsDialog({super.key});

  @override
  State<AddMoreProblemsDialog> createState() => _AddMoreProblemsDialogState();
}

class _AddMoreProblemsDialogState extends State<AddMoreProblemsDialog> {
  PlatformFile? _additionalPDF;
  ProblemGenerationParams? _params;
  bool _useOriginalPDF = true;

  Future<void> _uploadAdditionalPDF() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        allowMultiple: false,
      );

      if (result != null) {
        setState(() {
          _additionalPDF = result.files.first;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('PDFのアップロードに失敗しました: $e')),
        );
      }
    }
  }

  void _clearAdditionalPDF() {
    setState(() {
      _additionalPDF = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<ProblemGeneratorProvider>(context);
    final screenSize = MediaQuery.of(context).size;
    final dialogWidth = screenSize.width > 800 ? 800.0 : screenSize.width * 0.9;
    final dialogHeight = screenSize.height > 700 ? 700.0 : screenSize.height * 0.9;

    return Dialog(
      child: Container(
        width: dialogWidth,
        height: dialogHeight,
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.add_circle_outline, size: 24),
                const SizedBox(width: 8),
                const Text(
                  '問題を追加',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // PDF選択セクション
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'PDF選択',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    RadioListTile<bool>(
                      dense: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 0),
                      title: const Text('元のPDFを使用'),
                      subtitle: Text(provider.uploadedPDF?.name ?? ''),
                      value: true,
                      groupValue: _useOriginalPDF,
                      onChanged: (value) {
                        setState(() {
                          _useOriginalPDF = value!;
                          if (_useOriginalPDF) {
                            _additionalPDF = null;
                          }
                        });
                      },
                    ),
                    RadioListTile<bool>(
                      dense: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 0),
                      title: const Text('新しいPDFを使用'),
                      subtitle: _additionalPDF != null
                          ? Text(_additionalPDF!.name)
                          : const Text('PDFファイルを選択してください'),
                      value: false,
                      groupValue: _useOriginalPDF,
                      onChanged: (value) {
                        setState(() {
                          _useOriginalPDF = value!;
                        });
                      },
                    ),
                    if (!_useOriginalPDF) ...[
                      const SizedBox(height: 8),
                      if (_additionalPDF == null)
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _uploadAdditionalPDF,
                            icon: const Icon(Icons.upload_file),
                            label: const Text('PDFファイルを選択'),
                          ),
                        )
                      else
                        Row(
                          children: [
                            Icon(
                              Icons.picture_as_pdf,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(_additionalPDF!.name),
                            ),
                            TextButton(
                              onPressed: _clearAdditionalPDF,
                              child: const Text('変更'),
                            ),
                          ],
                        ),
                    ],
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // 問題生成条件
            Expanded(
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '問題生成条件',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Expanded(
                        child: SingleChildScrollView(
                          child: GenerationFormWidget(
                            onParamsChanged: (params) {
                              _params = params;
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            const SizedBox(height: 16),

            // アクションボタン
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('キャンセル'),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: ElevatedButton(
                    onPressed: provider.isLoading || _params == null || (!_useOriginalPDF && _additionalPDF == null)
                        ? null
                        : () async {
                            await provider.addMoreProblems(
                              additionalPDF: _useOriginalPDF ? null : _additionalPDF,
                              params: _params!,
                            );

                            if (provider.errorMessage == null && context.mounted) {
                              Navigator.of(context).pop();
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('${_params!.problemCount}問の問題を追加しました'),
                                  backgroundColor: Colors.green,
                                ),
                              );
                            }
                          },
                    child: provider.isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('問題を追加'),
                  ),
                ),
              ],
            ),

            if (provider.errorMessage != null)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Text(
                  provider.errorMessage!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}