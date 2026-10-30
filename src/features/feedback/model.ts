import type { FeedbackMessage } from '../../api/feedback.js';
export const FB_CHIPS = {
  down: [
    ['wrong_info', '정보가 틀려요'],
    ['too_long', '너무 길어요'],
    ['misunderstood', '질문을 잘못 이해했어요'],
    ['over_refusal', '거절이 과해요'],
    ['bad_source', '출처가 이상해요'],
    ['other', '기타'],
  ],
  up: [
    ['accurate', '정확해요'],
    ['concise', '간결해요'],
    ['helpful', '유용해요'],
    ['good_source', '출처가 좋아요'],
  ],
} as const;
export const FB_MAX = 140;
export type Snapshot = Pick<FeedbackMessage, 'feedback' | 'fbReasons' | 'fbComment'>;
export function snapshot(message: FeedbackMessage): Snapshot {
  return { feedback: message.feedback, fbReasons: message.fbReasons || [], fbComment: message.fbComment || '' };
}
