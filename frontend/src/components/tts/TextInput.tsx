import React from 'react';
import { X } from 'lucide-react';
import { Textarea } from '../ui/textarea';
import { Card, CardContent } from '../ui/card';

interface TextInputProps {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
  hasText: boolean;
  maxLength?: number;
  placeholder?: string;
}

export default function TextInput({
  value,
  onChange,
  onClear,
  hasText,
  maxLength = 3000,
  placeholder = "Enter the text you want to convert to speech..."
}: TextInputProps) {
  return (
    <Card className="">
      <CardContent>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-foreground">
            Text to Convert
          </label>
          {hasText && (
            <button
              onClick={onClear}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive duration-300"
              title="Clear text"
            >
              <X className="w-3 h-3" />
              Clear
            </button>
          )}
        </div>
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-32"
          placeholder={placeholder}
          maxLength={maxLength}
        />
        <div className="text-right text-sm text-muted-foreground mt-1">
          {value.length}/{maxLength} characters
        </div>
      </CardContent>
    </Card>
  );
} 