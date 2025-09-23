import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/problem_generator_provider.dart';
import '../models/problem_generation_params.dart';
import '../widgets/pdf_upload_widget.dart';
import '../widgets/generation_form_widget.dart';

class GenerationScreen extends StatefulWidget {
  const GenerationScreen({super.key});

  @override
  State<GenerationScreen> createState() => _GenerationScreenState();
}

class _GenerationScreenState extends State<GenerationScreen> {
  int _currentStep = 0;

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<ProblemGeneratorProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('問題を作成'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            provider.reset();
            context.go('/');
          },
        ),
      ),
      body: Theme(
        data: Theme.of(context).copyWith(
          colorScheme: Theme.of(context).colorScheme.copyWith(
                primary: Theme.of(context).colorScheme.primary,
              ),
        ),
        child: Stepper(
          currentStep: _currentStep,
          onStepContinue: () async {
            if (_currentStep == 0) {
              if (provider.uploadedPDF != null) {
                setState(() {
                  _currentStep = 1;
                });
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('PDFをアップロードしてください')),
                );
              }
            } else if (_currentStep == 1) {
              if (provider.params != null) {
                await provider.generateProblems();
                if (!provider.isLoading) {
                  if (provider.errorMessage != null) {
                    // エラーアラートを表示
                    if (mounted) {
                      showDialog(
                        context: context,
                        builder: (BuildContext context) {
                          return AlertDialog(
                            title: const Text('エラー'),
                            content: Text(provider.errorMessage!),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.of(context).pop();
                                },
                                child: const Text('OK'),
                              ),
                            ],
                          );
                        },
                      );
                    }
                  } else {
                    // 成功時は結果画面に遷移
                    if (mounted) {
                      context.go('/result');
                    }
                  }
                }
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('問題生成条件を入力してください')),
                );
              }
            }
          },
          onStepCancel: () {
            if (_currentStep > 0) {
              setState(() {
                _currentStep--;
              });
            }
          },
          onStepTapped: (step) {
            if (step <= _currentStep) {
              setState(() {
                _currentStep = step;
              });
            }
          },
          controlsBuilder: (context, details) {
            return Row(
              children: [
                if (_currentStep == 0)
                  ElevatedButton(
                    onPressed: provider.uploadedPDF != null
                        ? details.onStepContinue
                        : null,
                    child: const Text('次へ'),
                  )
                else
                  ElevatedButton(
                    onPressed: provider.isLoading
                        ? null
                        : details.onStepContinue,
                    child: provider.isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                            ),
                          )
                        : const Text('問題を生成'),
                  ),
                const SizedBox(width: 8),
                if (_currentStep > 0)
                  TextButton(
                    onPressed: details.onStepCancel,
                    child: const Text('戻る'),
                  ),
              ],
            );
          },
          steps: [
            Step(
              title: const Text('PDFアップロード'),
              content: const PdfUploadWidget(),
              isActive: _currentStep >= 0,
              state: _currentStep > 0
                  ? StepState.complete
                  : _currentStep == 0
                      ? StepState.editing
                      : StepState.disabled,
            ),
            Step(
              title: const Text('問題生成条件'),
              content: GenerationFormWidget(
                onParamsChanged: (params) {
                  provider.setParams(params);
                },
              ),
              isActive: _currentStep >= 1,
              state: _currentStep > 1
                  ? StepState.complete
                  : _currentStep == 1
                      ? StepState.editing
                      : StepState.disabled,
            ),
          ],
        ),
      ),
    );
  }
}