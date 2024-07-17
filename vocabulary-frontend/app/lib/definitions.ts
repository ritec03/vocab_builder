
export interface Task {
    id: number;
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
    learning_items: {
        id: number;
        item: string;
        pos: string;
        freq: number;
    }[];
}