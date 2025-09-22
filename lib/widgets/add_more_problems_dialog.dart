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
  bool _useOriginalPDF = false;

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
                      'PDFアップロード',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      '問題を追加するには新しいPDFファイルをアップロードしてください',
                      style: TextStyle(fontSize: 14, color: Colors.grey),
                    ),
                    const SizedBox(height: 16),
                    if (_additionalPDF == null)
                      Container(
                        width: double.infinity,
                        height: 100,
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: Theme.of(context).colorScheme.primary.withOpacity(0.5),
                            width: 2,
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: InkWell(
                          onTap: _uploadAdditionalPDF,
                          borderRadius: BorderRadius.circular(8),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.cloud_upload_outlined,
                                size: 32,
                                color: Theme.of(context).colorScheme.primary.withOpacity(0.6),
                              ),
                              const SizedBox(height: 8),
                              const Text('クリックしてPDFをアップロード'),
                            ],
                          ),
                        ),
                      )
                    else
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: Theme.of(context).colorScheme.primary.withOpacity(0.3),
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.picture_as_pdf,
                              color: Theme.of(context).colorScheme.primary,
                              size: 32,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _additionalPDF!.name,
                                    style: const TextStyle(fontWeight: FontWeight.w500),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  Text(
                                    '${(_additionalPDF!.size / 1024).toStringAsFixed(2)} KB',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            TextButton.icon(
                              onPressed: _clearAdditionalPDF,
                              icon: const Icon(Icons.refresh),
                              label: const Text('変更'),
                            ),
                          ],
                        ),
                      ),
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
                    onPressed: provider.isLoading || _params == null || _additionalPDF == null
                        ? null
                        : () async {
                            await provider.addMoreProblems(
                              additionalPDF: _additionalPDF,
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