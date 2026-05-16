import { Image as ImageIcon, Mic, ScanText, Video, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";

import { previewOcrImage, previewTts } from "@/lib/api";
import type { LearningEffectNextAction, LearningEffectReport } from "@/lib/types";

export type AssistantMultimodalActionId = "visual" | "tts_script" | "ocr" | "video_script";

export type AssistantMultimodalAction = {
  id: AssistantMultimodalActionId;
  title: string;
  detail: string;
  prompt: string;
  icon: LucideIcon;
};

export type AssistantResourcePreviewState = {
  actionId: AssistantMultimodalActionId | null;
  status: "idle" | "running" | "success" | "error";
  message: string;
  ttsUrl?: string;
  ttsVoice?: string;
  ttsContentType?: string;
  ocrText?: string;
  ocrProvider?: string;
  ocrFileName?: string;
  ocrPreviewUrl?: string;
};

export const ASSISTANT_MULTIMODAL_ACTIONS: AssistantMultimodalAction[] = [
  {
    id: "visual",
    title: "生成图解",
    detail: "结构图、流程图、知识关系图",
    prompt: "请基于当前课程资料和我的学习画像，把今天要学的概念生成一份图解方案。请输出图解标题、关键节点、连线说明，以及可用于前端展示的简短讲解文案。",
    icon: ImageIcon,
  },
  {
    id: "tts_script",
    title: "讯飞语音脚本",
    detail: "适配 TTS 的 60 秒讲解",
    prompt: "请把今天的学习重点改写成 60 秒语音讲解脚本，适合后续用科大讯飞 TTS 合成。要求口语化、分段清楚，并在结尾给一句复习提醒。",
    icon: Mic,
  },
  {
    id: "ocr",
    title: "识别讲义图片",
    detail: "对接讯飞 OCR 后做讲解",
    prompt: "我会上传或描述一张讲义/题目图片。请按照「讯飞 OCR 识别结果 + 课程资料 + 学习画像」的流程，先还原题意，再解释关键知识点，最后给出一条可执行练习建议。",
    icon: ScanText,
  },
  {
    id: "video_script",
    title: "短视频脚本",
    detail: "讲解镜头、旁白、练习收束",
    prompt: "请把今天的知识点整理成 90 秒短视频讲解脚本，包含镜头结构、画面提示、旁白和最后 1 道检查题，便于后续生成多模态学习资源。",
    icon: Video,
  },
];

const EMPTY_ASSISTANT_RESOURCE_PREVIEW: AssistantResourcePreviewState = {
  actionId: null,
  status: "idle",
  message: "",
};

export function useAssistantMultimodalPreview({
  report,
  nextActions,
  onUsePrompt,
}: {
  report?: LearningEffectReport;
  nextActions: LearningEffectNextAction[];
  onUsePrompt: (prompt: string) => void;
}) {
  const [preview, setPreview] = useState<AssistantResourcePreviewState>(EMPTY_ASSISTANT_RESOURCE_PREVIEW);
  const ttsUrlRef = useRef<string | null>(null);

  useEffect(
    () => () => {
      if (ttsUrlRef.current) URL.revokeObjectURL(ttsUrlRef.current);
    },
    [],
  );

  const replaceTtsUrl = useCallback((url: string | null) => {
    if (ttsUrlRef.current) URL.revokeObjectURL(ttsUrlRef.current);
    ttsUrlRef.current = url;
  }, []);

  const handleMultimodalAction = useCallback(
    async (action: AssistantMultimodalAction) => {
      if (action.id === "tts_script") {
        const script = assistantTtsPreviewScript(report, nextActions);
        setPreview({
          actionId: action.id,
          status: "running",
          message: "正在生成讯飞 TTS 试听。",
        });
        try {
          const result = await previewTts(script);
          const url = URL.createObjectURL(result.blob);
          replaceTtsUrl(url);
          setPreview({
            actionId: action.id,
            status: "success",
            message: "已生成一段可试听语音。",
            ttsUrl: url,
            ttsVoice: result.voice || "默认音色",
            ttsContentType: result.contentType,
          });
        } catch (error) {
          replaceTtsUrl(null);
          setPreview({
            actionId: action.id,
            status: "error",
            message: `TTS 预览未完成：${error instanceof Error ? error.message : "服务暂不可用"}`,
          });
          onUsePrompt(action.prompt);
        }
        return;
      }

      if (action.id === "ocr") {
        setPreview({
          actionId: action.id,
          status: "idle",
          message: "选择讲义或题目截图后，可直接得到 OCR 文本并交给助教讲解。",
        });
        return;
      }

      setPreview({
        actionId: action.id,
        status: "success",
        message: action.id === "visual" ? "图解方案请求已放入对话框。" : "短视频脚本请求已放入对话框。",
      });
      onUsePrompt(action.prompt);
    },
    [nextActions, onUsePrompt, replaceTtsUrl, report],
  );

  const handleOcrFileChange = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    setPreview({
      actionId: "ocr",
      status: "running",
      message: "正在识别图片文字。",
      ocrFileName: file.name,
    });
    try {
      const image = await readAssistantImageFile(file);
      const result = await previewOcrImage({
        image_base64: image.base64,
        encoding: assistantImageEncoding(file),
      });
      if (!result.success) {
        setPreview({
          actionId: "ocr",
          status: "error",
          message: `OCR 识别未完成：${result.error || "服务暂不可用"}`,
          ocrFileName: file.name,
          ocrPreviewUrl: image.preview,
        });
        return;
      }
      setPreview({
        actionId: "ocr",
        status: "success",
        message: "识别完成，可以交给助教继续讲解。",
        ocrText: result.text || "未识别到文字",
        ocrProvider: result.model || result.provider || "讯飞 OCR",
        ocrFileName: file.name,
        ocrPreviewUrl: image.preview,
      });
    } catch (error) {
      setPreview({
        actionId: "ocr",
        status: "error",
        message: error instanceof Error ? error.message : "图片读取失败",
        ocrFileName: file.name,
      });
    }
  }, []);

  const sendOcrToAssistant = useCallback(() => {
    if (!preview.ocrText) return;
    onUsePrompt(
      `这是讯飞 OCR 识别出的讲义或题目内容：\n\n${preview.ocrText}\n\n请结合课程资料和我的学习画像讲解关键知识点，并给出下一步练习。`,
    );
  }, [onUsePrompt, preview.ocrText]);

  return {
    actions: ASSISTANT_MULTIMODAL_ACTIONS,
    preview,
    handleMultimodalAction,
    handleOcrFileChange,
    sendOcrToAssistant,
  };
}

function readAssistantImageFile(file: File) {
  return new Promise<{ base64: string; preview: string }>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("图片读取失败"));
    reader.onload = () => {
      const preview = String(reader.result || "");
      resolve({
        base64: preview.includes(",") ? preview.split(",").pop() || "" : preview,
        preview,
      });
    };
    reader.readAsDataURL(file);
  });
}

function assistantImageEncoding(file: File) {
  const subtype = file.type.split("/")[1]?.toLowerCase();
  if (subtype === "jpeg") return "jpg";
  if (subtype) return subtype;
  const suffix = file.name.split(".").pop()?.toLowerCase();
  return suffix || "png";
}

function assistantTtsPreviewScript(report: LearningEffectReport | undefined, nextActions: LearningEffectNextAction[]) {
  const focus = report?.study_brief?.focus?.title || report?.study_brief?.headline || "今天的课程重点";
  const summary = report?.study_brief?.summary || "先抓住核心概念，再用一个小练习确认理解。";
  const nextAction = nextActions[0]?.title ? `接下来建议你做：${nextActions[0].title}。` : "接下来，用一道小题检验自己是否真的理解。";
  return `同学你好，今天我们先看 ${focus}。${summary}${nextAction} 如果你卡住了，先说出不确定的那一步，助教会继续拆开讲。`;
}
