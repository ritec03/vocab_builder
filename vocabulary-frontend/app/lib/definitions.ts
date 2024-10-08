
export interface Task {
    id: number;
    task_type: 'ONE_WAY_TRANSLATION' | 'FOUR_CHOICE';
    task_string: string;
    template: {
        id: number;
        template: string;
        task_type: string;
        starting_language: string;
        target_language: string;
    };
    correctAnswer: string;
    resources: Record<string,{
        id: number;
        resource: string;
        target_words: {
            id: number;
            item: string;
            pos: string;
            freq: number;
        }[];
    }>;
    learning_items: LexicalItem[];
}

export interface LexicalItem {
    id: number;
    item: string;
    pos: string;
    freq: number;
}

export interface Score {
    word: LexicalItem;
    score: number;
}