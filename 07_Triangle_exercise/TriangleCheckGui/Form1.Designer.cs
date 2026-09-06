namespace TriangleCheckGui
{
    partial class TriangleCheckMain
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.label1 = new System.Windows.Forms.Label();
            this.textSideA = new System.Windows.Forms.TextBox();
            this.label2 = new System.Windows.Forms.Label();
            this.txtSideB = new System.Windows.Forms.TextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.txtSideC = new System.Windows.Forms.TextBox();
            this.btnCleanC = new System.Windows.Forms.Button();
            this.btnCleanB = new System.Windows.Forms.Button();
            this.btnCleanA = new System.Windows.Forms.Button();
            this.txtResults = new System.Windows.Forms.TextBox();
            this.btnCleanData = new System.Windows.Forms.Button();
            this.btnCleanResults = new System.Windows.Forms.Button();
            this.btnHelp = new System.Windows.Forms.Button();
            this.btnExit = new System.Windows.Forms.Button();
            this.btnCalculate = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.label1.Location = new System.Drawing.Point(841, 10);
            this.label1.Name = "label1";
            this.label1.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.label1.Size = new System.Drawing.Size(94, 33);
            this.label1.TabIndex = 0;
            this.label1.Text = "צלע א\'";
            // 
            // textSideA
            // 
            this.textSideA.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.textSideA.Location = new System.Drawing.Point(641, 12);
            this.textSideA.Name = "textSideA";
            this.textSideA.Size = new System.Drawing.Size(194, 40);
            this.textSideA.TabIndex = 1;
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.label2.Location = new System.Drawing.Point(541, 10);
            this.label2.Name = "label2";
            this.label2.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.label2.Size = new System.Drawing.Size(94, 33);
            this.label2.TabIndex = 0;
            this.label2.Text = "צלע ב\'";
            // 
            // txtSideB
            // 
            this.txtSideB.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.txtSideB.Location = new System.Drawing.Point(330, 12);
            this.txtSideB.Name = "txtSideB";
            this.txtSideB.Size = new System.Drawing.Size(205, 40);
            this.txtSideB.TabIndex = 1;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.label3.Location = new System.Drawing.Point(235, 10);
            this.label3.Name = "label3";
            this.label3.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.label3.Size = new System.Drawing.Size(89, 33);
            this.label3.TabIndex = 0;
            this.label3.Text = "צלע ג\'";
            // 
            // txtSideC
            // 
            this.txtSideC.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.txtSideC.Location = new System.Drawing.Point(12, 12);
            this.txtSideC.Name = "txtSideC";
            this.txtSideC.Size = new System.Drawing.Size(217, 40);
            this.txtSideC.TabIndex = 1;
            // 
            // btnCleanC
            // 
            this.btnCleanC.Location = new System.Drawing.Point(154, 58);
            this.btnCleanC.Name = "btnCleanC";
            this.btnCleanC.Size = new System.Drawing.Size(75, 23);
            this.btnCleanC.TabIndex = 2;
            this.btnCleanC.Text = "נקה";
            this.btnCleanC.UseVisualStyleBackColor = true;
            this.btnCleanC.Click += new System.EventHandler(this.btnCleanC_Click);
            // 
            // btnCleanB
            // 
            this.btnCleanB.Location = new System.Drawing.Point(460, 58);
            this.btnCleanB.Name = "btnCleanB";
            this.btnCleanB.Size = new System.Drawing.Size(75, 23);
            this.btnCleanB.TabIndex = 2;
            this.btnCleanB.Text = "נקה";
            this.btnCleanB.UseVisualStyleBackColor = true;
            this.btnCleanB.Click += new System.EventHandler(this.btnCleanB_Click);
            // 
            // btnCleanA
            // 
            this.btnCleanA.Location = new System.Drawing.Point(760, 58);
            this.btnCleanA.Name = "btnCleanA";
            this.btnCleanA.Size = new System.Drawing.Size(75, 23);
            this.btnCleanA.TabIndex = 2;
            this.btnCleanA.Text = "נקה";
            this.btnCleanA.UseVisualStyleBackColor = true;
            this.btnCleanA.Click += new System.EventHandler(this.btnCleanA_Click);
            // 
            // txtResults
            // 
            this.txtResults.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.txtResults.Location = new System.Drawing.Point(12, 87);
            this.txtResults.Multiline = true;
            this.txtResults.Name = "txtResults";
            this.txtResults.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.txtResults.ScrollBars = System.Windows.Forms.ScrollBars.Both;
            this.txtResults.Size = new System.Drawing.Size(917, 375);
            this.txtResults.TabIndex = 3;
            // 
            // btnCleanData
            // 
            this.btnCleanData.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.btnCleanData.Location = new System.Drawing.Point(463, 468);
            this.btnCleanData.Name = "btnCleanData";
            this.btnCleanData.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.btnCleanData.Size = new System.Drawing.Size(166, 68);
            this.btnCleanData.TabIndex = 4;
            this.btnCleanData.Text = "נקה נתונים";
            this.btnCleanData.UseVisualStyleBackColor = true;
            this.btnCleanData.Click += new System.EventHandler(this.btnCleanData_Click);
            // 
            // btnCleanResults
            // 
            this.btnCleanResults.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.btnCleanResults.Location = new System.Drawing.Point(235, 468);
            this.btnCleanResults.Name = "btnCleanResults";
            this.btnCleanResults.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.btnCleanResults.Size = new System.Drawing.Size(166, 68);
            this.btnCleanResults.TabIndex = 4;
            this.btnCleanResults.Text = "נקה תוצאות";
            this.btnCleanResults.UseVisualStyleBackColor = true;
            this.btnCleanResults.Click += new System.EventHandler(this.btnCleanResults_Click);
            // 
            // btnHelp
            // 
            this.btnHelp.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.btnHelp.Location = new System.Drawing.Point(12, 468);
            this.btnHelp.Name = "btnHelp";
            this.btnHelp.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.btnHelp.Size = new System.Drawing.Size(36, 40);
            this.btnHelp.TabIndex = 4;
            this.btnHelp.Text = "?";
            this.btnHelp.UseVisualStyleBackColor = true;
            this.btnHelp.Click += new System.EventHandler(this.btnHelp_Click);
            // 
            // btnExit
            // 
            this.btnExit.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.btnExit.Location = new System.Drawing.Point(63, 468);
            this.btnExit.Name = "btnExit";
            this.btnExit.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.btnExit.Size = new System.Drawing.Size(100, 68);
            this.btnExit.TabIndex = 4;
            this.btnExit.Text = "יציאה";
            this.btnExit.UseVisualStyleBackColor = true;
            this.btnExit.Click += new System.EventHandler(this.btnExit_Click);
            // 
            // btnCalculate
            // 
            this.btnCalculate.Font = new System.Drawing.Font("Microsoft Sans Serif", 21.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(177)));
            this.btnCalculate.Location = new System.Drawing.Point(743, 468);
            this.btnCalculate.Name = "btnCalculate";
            this.btnCalculate.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.btnCalculate.Size = new System.Drawing.Size(186, 68);
            this.btnCalculate.TabIndex = 4;
            this.btnCalculate.Text = "חשב";
            this.btnCalculate.UseVisualStyleBackColor = true;
            this.btnCalculate.Click += new System.EventHandler(this.btnCalculate_Click);
            // 
            // TriangleCheckMain
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(940, 550);
            this.Controls.Add(this.btnCalculate);
            this.Controls.Add(this.btnExit);
            this.Controls.Add(this.btnHelp);
            this.Controls.Add(this.btnCleanResults);
            this.Controls.Add(this.btnCleanData);
            this.Controls.Add(this.txtResults);
            this.Controls.Add(this.btnCleanA);
            this.Controls.Add(this.btnCleanB);
            this.Controls.Add(this.btnCleanC);
            this.Controls.Add(this.txtSideC);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.txtSideB);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.textSideA);
            this.Controls.Add(this.label1);
            this.Name = "TriangleCheckMain";
            this.Text = "Triangle Check";
            this.Resize += new System.EventHandler(this.TriangleCheckMain_Resize);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.TextBox textSideA;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.TextBox txtSideB;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.TextBox txtSideC;
        private System.Windows.Forms.Button btnCleanC;
        private System.Windows.Forms.Button btnCleanB;
        private System.Windows.Forms.Button btnCleanA;
        private System.Windows.Forms.TextBox txtResults;
        private System.Windows.Forms.Button btnCleanData;
        private System.Windows.Forms.Button btnCleanResults;
        private System.Windows.Forms.Button btnHelp;
        private System.Windows.Forms.Button btnExit;
        private System.Windows.Forms.Button btnCalculate;
    }
}

