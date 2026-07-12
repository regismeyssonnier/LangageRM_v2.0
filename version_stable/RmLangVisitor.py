# Generated from RmLang.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .RmLangParser import RmLangParser
else:
    from RmLangParser import RmLangParser

# This class defines a complete generic visitor for a parse tree produced by RmLangParser.

class RmLangVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by RmLangParser#program.
    def visitProgram(self, ctx:RmLangParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#declaration.
    def visitDeclaration(self, ctx:RmLangParser.DeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#array_init.
    def visitArray_init(self, ctx:RmLangParser.Array_initContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#type.
    def visitType(self, ctx:RmLangParser.TypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#fonction.
    def visitFonction(self, ctx:RmLangParser.FonctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#param_list.
    def visitParam_list(self, ctx:RmLangParser.Param_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#param.
    def visitParam(self, ctx:RmLangParser.ParamContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#classe.
    def visitClasse(self, ctx:RmLangParser.ClasseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#class_member.
    def visitClass_member(self, ctx:RmLangParser.Class_memberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#constructeur.
    def visitConstructeur(self, ctx:RmLangParser.ConstructeurContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#fonction_membre.
    def visitFonction_membre(self, ctx:RmLangParser.Fonction_membreContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#bloc.
    def visitBloc(self, ctx:RmLangParser.BlocContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#instruction.
    def visitInstruction(self, ctx:RmLangParser.InstructionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#SimpleCompoundAssign.
    def visitSimpleCompoundAssign(self, ctx:RmLangParser.SimpleCompoundAssignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ArrayCompoundAssign.
    def visitArrayCompoundAssign(self, ctx:RmLangParser.ArrayCompoundAssignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#affectation.
    def visitAffectation(self, ctx:RmLangParser.AffectationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#affectation_membre.
    def visitAffectation_membre(self, ctx:RmLangParser.Affectation_membreContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#affectation_tableau.
    def visitAffectation_tableau(self, ctx:RmLangParser.Affectation_tableauContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#affectation_membre_tableau.
    def visitAffectation_membre_tableau(self, ctx:RmLangParser.Affectation_membre_tableauContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#method_call.
    def visitMethod_call(self, ctx:RmLangParser.Method_callContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#retour.
    def visitRetour(self, ctx:RmLangParser.RetourContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#appel_fonction.
    def visitAppel_fonction(self, ctx:RmLangParser.Appel_fonctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#condition.
    def visitCondition(self, ctx:RmLangParser.ConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#boucle_while.
    def visitBoucle_while(self, ctx:RmLangParser.Boucle_whileContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#boucle_for.
    def visitBoucle_for(self, ctx:RmLangParser.Boucle_forContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ForDecl.
    def visitForDecl(self, ctx:RmLangParser.ForDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ForExprInit.
    def visitForExprInit(self, ctx:RmLangParser.ForExprInitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#print_stmt.
    def visitPrint_stmt(self, ctx:RmLangParser.Print_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#println_stmt.
    def visitPrintln_stmt(self, ctx:RmLangParser.Println_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#input_stmt.
    def visitInput_stmt(self, ctx:RmLangParser.Input_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#argument_list.
    def visitArgument_list(self, ctx:RmLangParser.Argument_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#input_type.
    def visitInput_type(self, ctx:RmLangParser.Input_typeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#objectRef.
    def visitObjectRef(self, ctx:RmLangParser.ObjectRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#VarRef.
    def visitVarRef(self, ctx:RmLangParser.VarRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#MulExpr.
    def visitMulExpr(self, ctx:RmLangParser.MulExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#AndExpr.
    def visitAndExpr(self, ctx:RmLangParser.AndExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#EqualExpr.
    def visitEqualExpr(self, ctx:RmLangParser.EqualExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#BitwiseOrExpr.
    def visitBitwiseOrExpr(self, ctx:RmLangParser.BitwiseOrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#DerefExpr.
    def visitDerefExpr(self, ctx:RmLangParser.DerefExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#AssignExpr.
    def visitAssignExpr(self, ctx:RmLangParser.AssignExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#LessOrEqualExpr.
    def visitLessOrEqualExpr(self, ctx:RmLangParser.LessOrEqualExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#BoolLiteral.
    def visitBoolLiteral(self, ctx:RmLangParser.BoolLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#InputExpr.
    def visitInputExpr(self, ctx:RmLangParser.InputExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#BitwiseNotExpr.
    def visitBitwiseNotExpr(self, ctx:RmLangParser.BitwiseNotExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#CallExpr.
    def visitCallExpr(self, ctx:RmLangParser.CallExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#IntLiteral.
    def visitIntLiteral(self, ctx:RmLangParser.IntLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#NotExpr.
    def visitNotExpr(self, ctx:RmLangParser.NotExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ThisExpr.
    def visitThisExpr(self, ctx:RmLangParser.ThisExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#BitwiseAndExpr.
    def visitBitwiseAndExpr(self, ctx:RmLangParser.BitwiseAndExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#CharLiteral.
    def visitCharLiteral(self, ctx:RmLangParser.CharLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ArrayAccessExpr.
    def visitArrayAccessExpr(self, ctx:RmLangParser.ArrayAccessExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#FloatLiteral.
    def visitFloatLiteral(self, ctx:RmLangParser.FloatLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#SubExpr.
    def visitSubExpr(self, ctx:RmLangParser.SubExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#RightShiftExpr.
    def visitRightShiftExpr(self, ctx:RmLangParser.RightShiftExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#GreaterExpr.
    def visitGreaterExpr(self, ctx:RmLangParser.GreaterExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#AddExpr.
    def visitAddExpr(self, ctx:RmLangParser.AddExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#GreaterOrEqualExpr.
    def visitGreaterOrEqualExpr(self, ctx:RmLangParser.GreaterOrEqualExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#NotEqualExpr.
    def visitNotEqualExpr(self, ctx:RmLangParser.NotEqualExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ArrayLiteral.
    def visitArrayLiteral(self, ctx:RmLangParser.ArrayLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#OrExpr.
    def visitOrExpr(self, ctx:RmLangParser.OrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#LessExpr.
    def visitLessExpr(self, ctx:RmLangParser.LessExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#DivExpr.
    def visitDivExpr(self, ctx:RmLangParser.DivExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#StringLiteral.
    def visitStringLiteral(self, ctx:RmLangParser.StringLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#RefOfExpr.
    def visitRefOfExpr(self, ctx:RmLangParser.RefOfExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#MemberArrayAccessExpr.
    def visitMemberArrayAccessExpr(self, ctx:RmLangParser.MemberArrayAccessExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#UnaryPlusExpr.
    def visitUnaryPlusExpr(self, ctx:RmLangParser.UnaryPlusExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ParensExpr.
    def visitParensExpr(self, ctx:RmLangParser.ParensExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#ModExpr.
    def visitModExpr(self, ctx:RmLangParser.ModExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#MemberAccessExpr.
    def visitMemberAccessExpr(self, ctx:RmLangParser.MemberAccessExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#BitwiseXorExpr.
    def visitBitwiseXorExpr(self, ctx:RmLangParser.BitwiseXorExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#NullLiteral.
    def visitNullLiteral(self, ctx:RmLangParser.NullLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#CompoundAssignExpr.
    def visitCompoundAssignExpr(self, ctx:RmLangParser.CompoundAssignExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#LeftShiftExpr.
    def visitLeftShiftExpr(self, ctx:RmLangParser.LeftShiftExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#MethodCallExpr.
    def visitMethodCallExpr(self, ctx:RmLangParser.MethodCallExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by RmLangParser#UnaryMinusExpr.
    def visitUnaryMinusExpr(self, ctx:RmLangParser.UnaryMinusExprContext):
        return self.visitChildren(ctx)



del RmLangParser