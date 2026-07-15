grammar RmLang;

options {
    language = Python3;
}

program
    : (declaration | fonction | classe)* EOF
    ;

declaration
    : type ID ('=' expression)? ';'
    | 'ref' type ID '=' '&' ID ';'
    | type ID '[' expression ']' ('=' array_init)? ';'
    ;

array_init
    : '{' expression (',' expression)* '}'
    ;

type
    : type_base ('*')*
    ;

type_base
    : 'char' 
    | 'int' 
    | 'double' 
    | 'float' 
    | 'string' 
    | 'bool' 
    | 'void' 
    | ID
    ;

fonction
    : 'func' type? ID '(' param_list? ')' bloc
    ;

param_list
    : param (',' param)*
    ;

param
    : type ID
    ;

classe
    : 'class' ID '{' class_member* '}'
    ;

class_member
    : declaration
    | constructeur
    | fonction_membre
    ;

constructeur
    : 'constructor' ID '(' param_list? ')' bloc
    ;

fonction_membre
    : 'func' type? ID '(' param_list? ')' bloc
    ;

bloc
    : '{' instruction* '}'
    ;

instruction
    : declaration
    | affectation_composee
    | affectation
    | affectation_membre_tableau
    | affectation_membre
    | affectation_tableau
    | affectation_pointeur
    | affectation_pointeur_membre     // ptr->membre = valeur
    | method_call ';'
    | retour
    | appel_fonction ';'
    | input_stmt 
    | condition
    | boucle_while
    | boucle_for
    | 'break' ';'
    | 'continue' ';'
    | print_stmt ';'
    | println_stmt ';'
    | free_stmt ';'
    | file_open_stmt ';'
    | file_close_stmt ';'
    | file_read_stmt ';'
    | file_write_stmt ';'
    | file_read_binary_stmt ';'
    | file_write_binary_stmt ';'
    | ';'
    ;

// ============================================================
// AFFECTATIONS
// ============================================================

affectation
    : ID '=' expression ';'
    ;

affectation_composee
    : ID COMPOUND_ASSIGN expression ';'                    # SimpleCompoundAssign
    | ID '[' expression ']' COMPOUND_ASSIGN expression ';' # ArrayCompoundAssign
    | '*' expression COMPOUND_ASSIGN expression ';'        # PointerCompoundAssign
    ;

affectation_membre
    : objectRef '.' ID '=' expression ';'
    ;

affectation_tableau
    : ID '[' expression ']' '=' expression ';'
    ;

affectation_membre_tableau
    : objectRef '.' ID '[' expression ']' '=' expression ';'
    ;

affectation_pointeur
    : '*' expression '=' expression ';'
    ;

affectation_pointeur_membre
    : expression '->' ID '=' expression ';'       // ptr->membre = valeur
    ;

// ============================================================
// GESTION MÉMOIRE
// ============================================================

free_stmt
    : 'free' '(' expression ')'
    ;

// ============================================================
// FICHIERS
// ============================================================

file_mode
    : 'READ' | 'WRITE' | 'APPEND' | 'READ_BIN' | 'WRITE_BIN'
    ;

file_open_stmt
    : 'file_open' '(' expression ',' file_mode ')'
    ;

file_close_stmt
    : 'file_close' '(' expression ')'
    ;

file_read_stmt
    : 'file_read' '(' expression ',' ID ')'
    ;

file_write_stmt
    : 'file_write' '(' expression ',' expression ')'
    ;

file_read_binary_stmt
    : 'file_read_bin' '(' expression ',' type ',' ID ')'
    ;

file_write_binary_stmt
    : 'file_write_bin' '(' expression ',' expression ')'
    ;

// ============================================================
// DIVERS
// ============================================================

method_call
    : objectRef '.' ID '(' argument_list? ')'         // obj.methode()
    | expression '->' ID '(' argument_list? ')'       // ptr->methode()   <-- NOUVEAU
    ;

retour
    : 'return' expression? ';'
    ;

appel_fonction
    : ID '(' argument_list? ')'
    ;

condition
    : 'if' '(' expression ')' bloc ('else' 'if' '(' expression ')' bloc)* ('else' bloc)?
    ;

boucle_while
    : 'while' '(' expression ')' bloc
    ;

boucle_for
    : 'for' '(' for_init? ';' expression? ';' expression? ')' bloc
    ;

for_init
    : type ID ('=' expression)?   # ForDecl
    | expression                   # ForExprInit
    ;

print_stmt
    : 'print' '(' expression ')'
    ;

println_stmt
    : 'println' '(' expression ')'
    ;

input_stmt
    : 'input' '(' input_type? ')' ';'
    | 'input' '(' ')' ';'
    ;

argument_list
    : expression (',' expression)*
    ;

input_type
    : 'int' | 'double' | 'float' | 'string' | 'bool'
    ;

objectRef
    : ID
    | 'this'
    ;

// ============================================================
// EXPRESSION
// ============================================================

expression
    : objectRef '.' ID '[' expression ']'                 # MemberArrayAccessExpr
    | objectRef '.' ID '(' argument_list? ')'             # MethodCallExpr
    | objectRef '.' ID                                    # MemberAccessExpr
    | expression '->' ID '(' argument_list? ')'           # PtrMethodCallExpr    // ptr->methode()
    | expression '->' ID                                  # PtrMemberAccessExpr  // ptr->membre
    | 'input' '(' input_type? ')'                         # InputExpr
    | ID '[' expression ']' '.' ID '(' argument_list? ')' # ArrayMethodCallExpr
    | ID '[' expression ']'                               # ArrayAccessExpr
    | ID '(' argument_list? ')'                           # CallExpr
    | '(' expression ')'                                  # ParensExpr
    | 'new' type '[' expression ']'                       # NewArrayExpr
    | 'sizeof' '(' type ')'                               # SizeOfExpr
    | INT                                                 # IntLiteral
    | FLOAT                                               # FloatLiteral
    | STRING                                              # StringLiteral
    | BOOL                                                # BoolLiteral
    | CHAR                                                # CharLiteral
    | '[' expression (',' expression)* ']'                # ArrayLiteral
    | ID                                                  # VarRef
    | 'null'                                              # NullLiteral
    | 'this'                                              # ThisExpr
    | '&' ID                                              # RefOfExpr
    | '*' expression                                      # DerefExpr
    | '!' expression                                      # NotExpr
    | '~' expression                                      # BitwiseNotExpr
    | '-' expression                                      # UnaryMinusExpr
    | '+' expression                                      # UnaryPlusExpr
    | 'file_open' '(' expression ',' file_mode ')'         # FileOpenExpr
    | 'file_close' '(' expression ')'                      # FileCloseExpr
    | 'file_read' '(' expression ')'                       # FileReadExpr
    | 'file_read_bin' '(' expression ',' type ')'          # FileReadBinExpr
    | 'file_write' '(' expression ',' expression ')'       # FileWriteExpr
    | 'file_write_bin' '(' expression ',' expression ')'   # FileWriteBinExpr
    | 'file_eof' '(' expression ')'                        # FileEofExpr
    | expression '*' expression                           # MulExpr
    | expression '/' expression                           # DivExpr
    | expression '%' expression                           # ModExpr
    | expression '+' expression                           # AddExpr
    | expression '-' expression                           # SubExpr
    | expression '<<' expression                          # LeftShiftExpr
    | expression '>>' expression                          # RightShiftExpr
    | expression '<' expression                           # LessExpr
    | expression '>' expression                           # GreaterExpr
    | expression '<=' expression                          # LessOrEqualExpr
    | expression '>=' expression                          # GreaterOrEqualExpr
    | expression '==' expression                          # EqualExpr
    | expression '!=' expression                          # NotEqualExpr
    | expression '&' expression                           # BitwiseAndExpr
    | expression '^' expression                           # BitwiseXorExpr
    | expression '|' expression                           # BitwiseOrExpr
    | expression '&&' expression                          # AndExpr
    | expression '||' expression                          # OrExpr
    | <assoc=right> expression '=' expression             # AssignExpr
    | expression COMPOUND_ASSIGN expression               # CompoundAssignExpr
    ;

// ============================================================
// TOKENS
// ============================================================

CLASS       : 'class';
CONSTRUCTOR : 'constructor';
FUNC        : 'func';
RETURN      : 'return';
IF          : 'if';
ELSE        : 'else';
WHILE       : 'while';
FOR         : 'for';
BREAK       : 'break';
CONTINUE    : 'continue';
PRINT       : 'print';
PRINTLN     : 'println';
INPUT       : 'input';
REF         : 'ref';
THIS        : 'this';
NULL        : 'null';
NEW         : 'new';
SIZEOF      : 'sizeof';
FREE        : 'free';

CHAR_TYPE   : 'char';
INT_TYPE    : 'int';
DOUBLE_TYPE : 'double';
FLOAT_TYPE  : 'float';
STRING_TYPE : 'string';
BOOL_TYPE   : 'bool';
VOID_TYPE   : 'void';

FILE_OPEN      : 'file_open';
FILE_CLOSE     : 'file_close';
FILE_READ      : 'file_read';
FILE_WRITE     : 'file_write';
FILE_READ_BIN  : 'file_read_bin';
FILE_WRITE_BIN : 'file_write_bin';
FILE_EOF       : 'file_eof';
READ           : 'READ';
WRITE          : 'WRITE';
APPEND         : 'APPEND';
READ_BIN       : 'READ_BIN';
WRITE_BIN      : 'WRITE_BIN';

COMPOUND_ASSIGN
    : '+='
    | '-='
    | '*='
    | '/='
    | '%='
    | '&='
    | '|='
    | '^='
    | '<<='
    | '>>='
    ;

BOOL
    : 'true' | 'false'
    ;

ID
    : [a-zA-Z_][a-zA-Z0-9_]*
    ;

CHAR : '\'' ( ~['\\] | '\\' . ) '\'' ;

INT
    : [0-9]+
    ;

FLOAT
    : [0-9]+ '.' [0-9]+
    ;

STRING
    : '"' (~["\r\n])* '"'
    ;

COMMENT_SINGLE
    : '//' ~[\r\n]* -> skip
    ;

COMMENT_MULTI
    : '/*' .*? '*/' -> skip
    ;

WS
    : [ \r\n\t]+ -> skip
    ;

UNKNOWN
    : . -> skip
    ;