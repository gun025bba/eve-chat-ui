export type Rating = 'up' | 'down' | null;
export type FeedbackMessage = { id?: string; feedback?: Rating; fbReasons?: string[]; fbComment?: string };
export function feedbackPayload(message: FeedbackMessage) {
  return {
    id: message.id,
    rating: message.feedback,
    reasons: message.feedback ? [...(message.fbReasons || [])] : [],
    comment: message.feedback ? message.fbComment || '' : '',
  };
}
